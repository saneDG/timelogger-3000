import json
import re
import time
import threading
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.timeline import chunk_segments


PROMPT_VERSION = "task-classifier-v4"


class ClassificationGroup(BaseModel):
    segment_ids: List[str] = Field(min_length=1)
    task_label: str = Field(min_length=1, max_length=160)
    project_hint: Optional[str] = Field(default=None, max_length=120)
    confidence: float = Field(ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> Any:
        # Confidence is advisory, not authoritative. Some local models ignore the
        # schema range and emit values such as 1.8 or -0.2; clamp those rather
        # than failing an otherwise valid classification.
        if isinstance(value, str) and value.strip().endswith("%"):
            value = float(value.strip()[:-1]) / 100
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        return value


class ClassificationResponse(BaseModel):
    groups: List[ClassificationGroup]


class TimesheetSummary(BaseModel):
    entry_id: str
    summary: str = Field(min_length=3, max_length=300)


class TimesheetSummaryResponse(BaseModel):
    entries: List[TimesheetSummary]


class LMStudioError(RuntimeError):
    pass


class GeneratedTextQualityError(LMStudioError):
    pass


class LMStudioCancelled(LMStudioError):
    pass


class LMStudioService:
    def __init__(self, base_url: str, timeout_seconds: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._active_lock = threading.Lock()
        self._active_requests: Dict[str, Dict[str, Any]] = {}
        self._cancelled_runs: Set[str] = set()

    def cancel(self, run_id: str) -> bool:
        """Close the active streaming connection so LM Studio stops generation."""
        with self._active_lock:
            self._cancelled_runs.add(run_id)
            active = self._active_requests.get(run_id)
        if not active:
            return False
        response = active.get("response")
        client = active.get("client")
        try:
            if response is not None:
                response.close()
        finally:
            if client is not None:
                client.close()
        return True

    def _raise_if_cancelled(self, run_id: Optional[str]) -> None:
        if not run_id:
            return
        with self._active_lock:
            cancelled = run_id in self._cancelled_runs
        if cancelled:
            raise LMStudioCancelled("LM Studio generation was cancelled.")

    def _completion_content(
        self, request: Dict[str, Any], run_id: Optional[str] = None
    ) -> Any:
        """Read an OpenAI completion as SSE so closing it cancels generation."""
        self._raise_if_cancelled(run_id)
        streaming_request = {**request, "stream": True}
        client = httpx.Client(timeout=self.timeout_seconds)
        active = {"client": client, "response": None}
        if run_id:
            with self._active_lock:
                self._active_requests[run_id] = active
        response = None
        try:
            response = client.send(
                client.build_request(
                    "POST", self.base_url + "/chat/completions", json=streaming_request
                ),
                stream=True,
            )
            active["response"] = response
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                payload = response.read()
                self._raise_if_cancelled(run_id)
                return json.loads(payload)["choices"][0]["message"]["content"]
            pieces: List[str] = []
            for line in response.iter_lines():
                self._raise_if_cancelled(run_id)
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    pieces.append(delta["content"])
            self._raise_if_cancelled(run_id)
            return "".join(pieces)
        except (httpx.HTTPError, RuntimeError) as exc:
            self._raise_if_cancelled(run_id)
            raise exc
        finally:
            if run_id:
                with self._active_lock:
                    if self._active_requests.get(run_id) is active:
                        self._active_requests.pop(run_id, None)
            if response is not None:
                response.close()
            client.close()

    def status(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(self.base_url + "/models")
                response.raise_for_status()
                models = [item["id"] for item in response.json().get("data", [])]
            return {"connected": True, "models": models}
        except Exception as exc:
            return {"connected": False, "models": [], "error": str(exc)}

    def classify(
        self, segments: List[Dict[str, Any]], model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if not segments:
            return model or "none", []
        selected_model = model or self._default_model()
        tasks: List[Dict[str, Any]] = []
        for chunk in chunk_segments(segments):
            response = (
                self._classify_chunk(chunk, selected_model, run_id=run_id)
                if run_id else self._classify_chunk(chunk, selected_model)
            )
            assigned = {
                segment_id for group in response.groups for segment_id in group.segment_ids
            }
            missing = [item for item in chunk if item["id"] not in assigned]
            if missing:
                repair = (
                    self._classify_chunk(
                        missing, selected_model, repair=True, run_id=run_id
                    )
                    if run_id else self._classify_chunk(missing, selected_model, repair=True)
                )
                response = ClassificationResponse(groups=response.groups + repair.groups)
            tasks.extend(self._tasks_from_response(chunk, response))
        return selected_model, self._consolidate_tasks(segments, tasks)

    def summarize_entries(
        self, payload: Dict[str, Any], model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, str]]:
        selected_model = model or self._default_model()
        entries = payload.get("entries", [])
        if not entries:
            return selected_model, {}
        # Summarize one entry per request. Small local models frequently omit or
        # duplicate IDs in a multi-entry response even with strict JSON schema.
        # Single-entry requests make complete coverage deterministic.
        summaries: Dict[str, str] = {}
        for index, source_entry in enumerate(entries, 1):
            reference = "E%03d" % index
            local_payload = dict(payload)
            local_payload["entries"] = [{**source_entry, "entry_id": reference}]
            response_schema = TimesheetSummaryResponse.model_json_schema()
            summary_properties = response_schema["$defs"]["TimesheetSummary"]["properties"]
            summary_properties["entry_id"] = {"type": "string", "enum": [reference]}
            summary_properties["summary"]["maxLength"] = 300
            request = {
                "model": selected_model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Write a precise professional timesheet description of the work evidenced "
                            "by the supplied entry. Preserve concrete actions, features, fixes, tests, "
                            "repository context, and other technical details present in the source. "
                            "Prefer one or two informative sentences rather than a vague short label. "
                            "Combine related actions without repeating yourself. Return exactly one entry "
                            "using the supplied entry_id. Do not change the project, duration, or ID, and "
                            "do not infer or invent work that is not supported. Use plain natural language "
                            "and stay within 300 characters."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(local_payload, ensure_ascii=False),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "timesheet_summary",
                        "strict": True,
                        "schema": response_schema,
                    },
                },
            }
            result = (
                self._request_timesheet_summary(request, run_id=run_id)
                if run_id else self._request_timesheet_summary(request)
            )
            if len(result.entries) != 1:
                raise LMStudioError(
                    "LM Studio must return exactly one summary for entry %s." % reference
                )
            returned = result.entries[0]
            normalized_id = returned.entry_id.strip().casefold()
            if normalized_id not in {reference.casefold(), str(index)}:
                raise LMStudioError(
                    "LM Studio returned an unknown timesheet entry ID '%s'."
                    % returned.entry_id
                )
            raw_summary = returned.summary
            summary = self._clean_generated_text(raw_summary)
            if self._generated_text_is_invalid(raw_summary, max_length=300) or not summary:
                # A malformed sentence must not invalidate the entire timesheet.
                # The already-sanitized local description is a safe fallback.
                summary = self._fallback_timesheet_summary(source_entry)
            summaries[source_entry["entry_id"]] = summary
        return selected_model, summaries

    @staticmethod
    def _fallback_timesheet_summary(entry: Dict[str, Any]) -> str:
        description = LMStudioService._clean_generated_text(
            str(entry.get("local_description") or "")
        ) or "Work activity"
        parts = [part.strip() for part in description.split(";") if part.strip()]
        summary = "; ".join(parts[:4]) or "Work activity"
        if len(summary) > 300:
            summary = summary[:297].rsplit(" ", 1)[0].rstrip(" -–—:;,.…?!") + "..."
        return summary

    def _request_timesheet_summary(
        self, request: Dict[str, Any], run_id: Optional[str] = None
    ) -> TimesheetSummaryResponse:
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                content = self._completion_content(request, run_id)
                parsed = json.loads(content) if isinstance(content, str) else content
                return TimesheetSummaryResponse.model_validate(parsed)
            except LMStudioCancelled:
                raise
            except (
                httpx.HTTPError,
                KeyError,
                TypeError,
                json.JSONDecodeError,
                ValidationError,
            ) as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.4)
        raise LMStudioError(
            "LM Studio returned an invalid timesheet summary: %s" % last_error
        )

    def _default_model(self) -> str:
        status = self.status()
        if not status["connected"]:
            raise LMStudioError("LM Studio is unavailable: %s" % status.get("error", "unknown error"))
        if not status["models"]:
            raise LMStudioError("LM Studio is running, but no model is loaded.")
        return status["models"][0]

    def _classify_chunk(
        self, segments: List[Dict[str, Any]], model: str, repair: bool = False,
        run_id: Optional[str] = None,
    ) -> ClassificationResponse:
        # Short references are easier for small local models to reproduce than UUIDs.
        # They are mapped back to authoritative segment IDs before validation/storage.
        reference_to_id = {
            "S%03d" % (index + 1): item["id"] for index, item in enumerate(segments)
        }
        segment_payload = [
            {
                "id": reference,
                "start": item["start"],
                "end": item["end"],
                "duration_seconds": item["duration_seconds"],
                "app": item["app"],
                "category": item["category"],
                "title": item.get("title") or None,
                "domain": item.get("domain"),
            }
            for reference, item in zip(reference_to_id, segments)
        ]
        system_prompt = (
            "You turn a private local computer-activity timeline into the small set of entries "
            "a human would realistically put in a timesheet. Infer focused work blocks, the likely "
            "start of work, and meaningful project/context switches. Group editor, terminal, browser, "
            "and communication activity together when they support the same goal. Do not make a task "
            "for every app or title change, and do not split one continuous project unnecessarily. "
            "Assign every segment exactly once, including unclear or incidental activity. Use only IDs "
            "supplied by the user. Do not calculate or alter times or durations. Use a concise factual "
            "task_label and a stable project_hint when there is evidence; project_hint may be null. "
            "Labels must be detailed, factual plain natural language under 160 characters. Preserve "
            "concrete actions and technical evidence such as implemented features, fixes, tests, and "
            "Git commit subjects when supplied. Never emit model control "
            "tokens, repeated punctuation, placeholders, or uncertain project names such as '???'. "
            "Return JSON matching the provided schema and no commentary."
        )
        if repair:
            system_prompt += (
                " This is a coverage repair request containing segments omitted previously. You must "
                "include every supplied ID exactly once; group unclear items into sensible broader blocks."
            )
        user_prompt = "Classify these timeline segments:\n" + json.dumps(
            segment_payload, ensure_ascii=False
        )
        response_schema = ClassificationResponse.model_json_schema()
        response_schema["$defs"]["ClassificationGroup"]["properties"]["segment_ids"][
            "items"
        ] = {"type": "string", "enum": list(reference_to_id)}
        request = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "activity_classification",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                content = self._completion_content(request, run_id)
                if isinstance(content, str):
                    content = content.strip()
                    if content.startswith("```"):
                        content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
                    parsed = json.loads(content)
                else:
                    parsed = content
                classification = ClassificationResponse.model_validate(parsed)
                invalid_groups = self._invalid_text_groups(classification)
                if invalid_groups and attempt == 0:
                    request["messages"].append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous JSON contained malformed labels, special model tokens, "
                                "or punctuation gibberish. Regenerate clean concise labels using normal "
                                "words only. Do not emit tokens such as <|reserved...|>, repeated question "
                                "marks, or uncertain placeholder project names."
                            ),
                        }
                    )
                    raise GeneratedTextQualityError(
                        "The model generated malformed task text."
                    )
                classification = self._sanitize_classification_text(
                    classification, invalid_groups
                )
                classification = self._resolve_segment_references(
                    classification, reference_to_id
                )
                # Local models occasionally repeat an ID in a second, overlapping
                # group. Keep its first assignment and let coverage repair handle
                # genuinely missing segments rather than failing the entire run.
                classification = self._deduplicate_assignments(classification)
                self._validate_assignments(segments, classification)
                return classification
            except LMStudioCancelled:
                raise
            except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValidationError, LMStudioError) as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.4)
        raise LMStudioError("LM Studio returned an invalid classification: %s" % last_error)

    @staticmethod
    def _clean_generated_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = unicodedata.normalize("NFKC", value)
        value = re.sub(r"<\|[^>]*\|>", "", value)
        value = " ".join(value.split()).strip(" -–—:;,.…?！!")
        return value or None

    @staticmethod
    def _generated_text_is_invalid(value: Optional[str], max_length: int = 160) -> bool:
        if value is None:
            return False
        normalized = unicodedata.normalize("NFKC", value)
        if re.search(r"<\|[^>]*\|>", normalized):
            return True
        if re.search(r"[?.!,;:…]{6,}", normalized):
            return True
        if len(normalized) > max_length:
            return True
        visible = [character for character in normalized if not character.isspace()]
        if not visible:
            return True
        punctuation = sum(
            1 for character in visible if unicodedata.category(character).startswith("P")
        )
        letters = sum(1 for character in visible if character.isalpha())
        return letters < 3 or punctuation / len(visible) > 0.30

    @staticmethod
    def _invalid_text_groups(response: ClassificationResponse) -> Set[int]:
        return {
            index
            for index, group in enumerate(response.groups)
            if LMStudioService._generated_text_is_invalid(group.task_label)
            or LMStudioService._generated_text_is_invalid(group.project_hint)
        }

    @staticmethod
    def _sanitize_classification_text(
        response: ClassificationResponse, invalid_groups: Set[int]
    ) -> ClassificationResponse:
        groups = []
        for index, group in enumerate(response.groups):
            if index in invalid_groups:
                groups.append(
                    group.model_copy(
                        update={
                            "task_label": "Unclassified work",
                            "project_hint": None,
                            "confidence": min(group.confidence, 0.25),
                        }
                    )
                )
            else:
                groups.append(
                    group.model_copy(
                        update={
                            "task_label": LMStudioService._clean_generated_text(
                                group.task_label
                            )
                            or "Unclassified work",
                            "project_hint": LMStudioService._clean_generated_text(
                                group.project_hint
                            ),
                        }
                    )
                )
        return ClassificationResponse(groups=groups)

    @staticmethod
    def _resolve_segment_references(
        response: ClassificationResponse, reference_to_id: Dict[str, str]
    ) -> ClassificationResponse:
        aliases: Dict[str, str] = {}
        for reference, segment_id in reference_to_id.items():
            number = str(int(reference[1:]))
            aliases[reference.upper()] = segment_id
            aliases[number] = segment_id
        groups = []
        for group in response.groups:
            resolved = []
            for supplied_id in group.segment_ids:
                normalized = str(supplied_id).strip().upper()
                segment_id = aliases.get(normalized)
                if segment_id is None:
                    raise LMStudioError(
                        "The model referenced an unknown segment ID '%s'." % supplied_id
                    )
                resolved.append(segment_id)
            groups.append(group.model_copy(update={"segment_ids": resolved}))
        return ClassificationResponse(groups=groups)

    @staticmethod
    def _deduplicate_assignments(
        response: ClassificationResponse,
    ) -> ClassificationResponse:
        assigned: Set[str] = set()
        groups = []
        for group in response.groups:
            unique_ids = []
            for segment_id in group.segment_ids:
                if segment_id not in assigned:
                    assigned.add(segment_id)
                    unique_ids.append(segment_id)
            if unique_ids:
                groups.append(group.model_copy(update={"segment_ids": unique_ids}))
        return ClassificationResponse(groups=groups)

    @staticmethod
    def _validate_assignments(
        segments: List[Dict[str, Any]], response: ClassificationResponse
    ) -> None:
        known = {item["id"] for item in segments}
        assigned: Set[str] = set()
        for group in response.groups:
            for segment_id in group.segment_ids:
                if segment_id not in known:
                    raise LMStudioError("The model referenced an unknown segment ID.")
                if segment_id in assigned:
                    raise LMStudioError("The model assigned a segment more than once.")
                assigned.add(segment_id)

    @staticmethod
    def _tasks_from_response(
        segments: List[Dict[str, Any]], response: ClassificationResponse
    ) -> List[Dict[str, Any]]:
        by_id = {item["id"]: item for item in segments}
        assigned: Set[str] = set()
        tasks: List[Dict[str, Any]] = []
        for group in response.groups:
            group_segments = [by_id[segment_id] for segment_id in group.segment_ids]
            assigned.update(group.segment_ids)
            malformed = group.task_label == "Unclassified work"
            tasks.append(
                LMStudioService._make_task(
                    group_segments,
                    (
                        LMStudioService._fallback_label(group_segments)
                        if malformed
                        else group.task_label.strip()
                    ),
                    group.project_hint.strip() if group.project_hint else None,
                    group.confidence,
                    "unassigned" if malformed else "classified",
                )
            )
        missing = [segment for segment in segments if segment["id"] not in assigned]
        for group in LMStudioService._group_unassigned_segments(missing):
            tasks.append(
                LMStudioService._make_task(
                    group,
                    LMStudioService._fallback_label(group),
                    None,
                    0,
                    "unassigned",
                )
            )
        return tasks

    @staticmethod
    def _group_unassigned_segments(
        segments: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        groups: List[List[Dict[str, Any]]] = []
        for segment in sorted(segments, key=lambda item: item["start"]):
            if not groups:
                groups.append([segment])
                continue
            previous = groups[-1][-1]
            gap = (
                datetime.fromisoformat(segment["start"])
                - datetime.fromisoformat(previous["end"])
            ).total_seconds()
            same_context = (
                segment.get("session") == previous.get("session")
                and segment.get("app") == previous.get("app")
                and segment.get("domain") == previous.get("domain")
                and (segment.get("category") or [None])[0]
                == (previous.get("category") or [None])[0]
            )
            both_brief = (
                segment["duration_seconds"] < 60
                and previous["duration_seconds"] < 60
            )
            if (
                segment.get("session") == previous.get("session")
                and gap <= 180
                and (same_context or both_brief)
            ):
                groups[-1].append(segment)
            else:
                groups.append([segment])
        return groups

    @staticmethod
    def _fallback_label(segments: List[Dict[str, Any]]) -> str:
        domains = {item.get("domain") for item in segments if item.get("domain")}
        apps = {item.get("app") for item in segments if item.get("app")}
        categories = {
            item["category"][0]
            for item in segments
            if item.get("category") and item["category"][0] != "Uncategorized"
        }
        if len(domains) == 1:
            return "Activity on %s" % next(iter(domains))
        if len(apps) == 1:
            return "Activity in %s" % next(iter(apps))
        if len(categories) == 1:
            return "%s activity" % next(iter(categories))
        return "Unclassified activity"

    @staticmethod
    def _consolidate_tasks(
        segments: List[Dict[str, Any]], tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Collapse model output into human-sized, timesheet-like entries."""
        if not tasks:
            return []
        by_id = {item["id"]: item for item in segments}
        ordered = sorted(tasks, key=lambda item: item["start"])

        # Merge adjacent entries when the model gave them the same project/label,
        # or when a brief entry is clearly part of the same app/domain context.
        consolidated: List[Dict[str, Any]] = []
        for task in ordered:
            if consolidated and LMStudioService._tasks_are_compatible(
                consolidated[-1], task, by_id
            ):
                LMStudioService._merge_task(consolidated[-1], task)
            else:
                consolidated.append(dict(task))

        # A sub-minute item is not a useful standalone time entry. Attach it to
        # the closest block in the same work session; otherwise collect brief
        # leftovers into one miscellaneous entry per session.
        index = 0
        leftovers: Dict[int, List[Dict[str, Any]]] = {}
        while index < len(consolidated):
            task = consolidated[index]
            if task["duration_seconds"] >= 60 or len(consolidated) == 1:
                index += 1
                continue
            session = LMStudioService._task_session(task, by_id)
            candidates = []
            if index > 0 and LMStudioService._task_session(consolidated[index - 1], by_id) == session:
                candidates.append((LMStudioService._task_gap(consolidated[index - 1], task), index - 1))
            if index + 1 < len(consolidated) and LMStudioService._task_session(consolidated[index + 1], by_id) == session:
                candidates.append((LMStudioService._task_gap(task, consolidated[index + 1]), index + 1))
            nearby = [candidate for candidate in candidates if candidate[0] <= 300]
            if nearby:
                _, target_index = min(nearby)
                LMStudioService._merge_task(consolidated[target_index], task, keep_target_label=True)
                consolidated.pop(index)
                if target_index > index:
                    target_index -= 1
                continue
            leftovers.setdefault(session, []).append(task)
            consolidated.pop(index)

        for session_tasks in leftovers.values():
            base = dict(session_tasks[0])
            base["label"] = "Brief miscellaneous activity"
            base["project_hint"] = None
            base["status"] = "consolidated"
            for task in session_tasks[1:]:
                LMStudioService._merge_task(base, task, keep_target_label=True)
            consolidated.append(base)
        return sorted(consolidated, key=lambda item: item["start"])

    @staticmethod
    def _tasks_are_compatible(
        left: Dict[str, Any], right: Dict[str, Any], segments: Dict[str, Dict[str, Any]]
    ) -> bool:
        if LMStudioService._task_session(left, segments) != LMStudioService._task_session(right, segments):
            return False
        if LMStudioService._task_gap(left, right) > 300:
            return False
        left_project = (left.get("project_hint") or "").strip().casefold()
        right_project = (right.get("project_hint") or "").strip().casefold()
        if left_project and left_project == right_project:
            return left["duration_seconds"] < 300 or right["duration_seconds"] < 300
        if left["label"].strip().casefold() == right["label"].strip().casefold():
            return True
        if min(left["duration_seconds"], right["duration_seconds"]) >= 60:
            return False
        left_context = LMStudioService._task_context(left, segments)
        right_context = LMStudioService._task_context(right, segments)
        return bool(left_context & right_context)

    @staticmethod
    def _task_context(
        task: Dict[str, Any], segments: Dict[str, Dict[str, Any]]
    ) -> Set[str]:
        context: Set[str] = set()
        for segment_id in task["segment_ids"]:
            segment = segments[segment_id]
            context.add("app:" + segment["app"].casefold())
            if segment.get("domain"):
                context.add("domain:" + segment["domain"].casefold())
            if segment.get("category"):
                context.add("category:" + segment["category"][0].casefold())
        return context

    @staticmethod
    def _task_session(task: Dict[str, Any], segments: Dict[str, Dict[str, Any]]) -> int:
        return min(segments[segment_id].get("session", 0) for segment_id in task["segment_ids"])

    @staticmethod
    def _task_gap(left: Dict[str, Any], right: Dict[str, Any]) -> float:
        return max(
            0.0,
            (
                datetime.fromisoformat(right["start"])
                - datetime.fromisoformat(left["end"])
            ).total_seconds(),
        )

    @staticmethod
    def _merge_task(
        target: Dict[str, Any], source: Dict[str, Any], keep_target_label: bool = False
    ) -> None:
        if not keep_target_label and target["label"] in {
            "Unclassified activity", "Brief miscellaneous activity"
        }:
            target["label"] = source["label"]
        if not target.get("project_hint") and source.get("project_hint"):
            target["project_hint"] = source["project_hint"]
        target["duration_seconds"] = round(
            target["duration_seconds"] + source["duration_seconds"], 3
        )
        target["start"] = min(target["start"], source["start"])
        target["end"] = max(target["end"], source["end"])
        target["confidence"] = min(target["confidence"], source["confidence"])
        target["status"] = "consolidated"
        target["segment_ids"] = list(
            dict.fromkeys(target["segment_ids"] + source["segment_ids"])
        )

    @staticmethod
    def _make_task(
        segments: List[Dict[str, Any]],
        label: str,
        project_hint: Optional[str],
        confidence: float,
        status: str,
    ) -> Dict[str, Any]:
        return {
            "id": str(uuid4()),
            "label": label,
            "project_hint": project_hint,
            "confidence": round(float(confidence), 3),
            "duration_seconds": round(
                sum(float(item["duration_seconds"]) for item in segments), 3
            ),
            "start": min(item["start"] for item in segments),
            "end": max(item["end"] for item in segments),
            "status": status,
            "segment_ids": [item["id"] for item in segments],
        }
