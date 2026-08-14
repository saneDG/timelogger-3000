import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4


GENERIC_PROJECTS = {"", "unknown", "none", "unassigned", "project", "???"}


def _tokens(value: str) -> Set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9._-]+", value.casefold())
        if len(token) >= 3
    }


def assign_project(
    task: Dict[str, Any],
    segments: Dict[str, Dict[str, Any]],
    projects: List[Dict[str, Any]],
) -> Tuple[Optional[str], float, str]:
    evidence = " ".join(
        [task.get("label", ""), task.get("project_hint") or ""]
        + [
            " ".join(
                [segment.get("app", ""), segment.get("domain") or ""]
            )
            for segment_id in task["segment_ids"]
            for segment in [segments[segment_id]]
        ]
    ).casefold()
    evidence_tokens = _tokens(evidence)
    best: Tuple[float, Optional[str], str] = (0, None, "unassigned")
    for project in projects:
        score = 0.0
        source = []
        names = [project["name"]] + project.get("aliases", [])
        if any(name.casefold() in evidence for name in names if len(name.strip()) >= 3):
            score += 5
            source.append("name")
        domain_matches = [
            domain for domain in project.get("domains", [])
            if domain.casefold() in evidence
        ]
        if domain_matches:
            score += 4
            source.append("domain")
        keyword_matches = _tokens(" ".join(project.get("keywords", []))) & evidence_tokens
        score += min(4, len(keyword_matches) * 1.5)
        if keyword_matches:
            source.append("keyword")
        hint = (task.get("project_hint") or "").strip().casefold()
        if hint and hint not in GENERIC_PROJECTS and any(
            hint == name.casefold() or hint in name.casefold() or name.casefold() in hint
            for name in names
        ):
            score += 5
            source.append("model_hint")
        confidence = min(1.0, score / 7)
        if score > best[0]:
            best = (score, project["id"], "+".join(source) or "unassigned")
    if best[0] < 2.5:
        return None, 0, "unassigned"
    return best[1], min(1.0, best[0] / 7), best[2]


def _round_seconds(seconds: float, increment_minutes: int) -> int:
    increment = increment_minutes * 60
    return max(increment, int(math.floor((seconds + increment / 2) / increment) * increment))


def build_entries(
    tasks: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    projects: List[Dict[str, Any]],
    increment_minutes: int = 5,
) -> List[Dict[str, Any]]:
    by_segment = {item["id"]: item for item in segments}
    project_by_id = {item["id"]: item for item in projects}
    provisional = []
    previous_project: Optional[str] = None
    for task in sorted(tasks, key=lambda item: item["start"]):
        project_id, confidence, source = assign_project(task, by_segment, projects)
        # Timeline continuity prevents a weak one-off suggestion from causing a
        # project switch in the middle of a sustained block.
        if project_id is None and previous_project and task["duration_seconds"] < 300:
            project_id, confidence, source = previous_project, 0.45, "timeline_continuity"
        if project_id:
            previous_project = project_id
        provisional.append(
            {
                "id": str(uuid4()), "project_id": project_id,
                "start": task["start"], "end": task["end"],
                "raw_seconds": task["duration_seconds"],
                "local_description": task["label"],
                "assignment_confidence": confidence,
                "assignment_source": source,
                "task_ids": [task["id"]],
            }
        )

    entries: List[Dict[str, Any]] = []
    for item in provisional:
        if entries:
            previous = entries[-1]
            gap = max(0, (datetime.fromisoformat(item["start"]) - datetime.fromisoformat(previous["end"])).total_seconds())
            same_project = previous["project_id"] == item["project_id"]
            same_generic = not previous["project_id"] and not item["project_id"]
            if gap <= 600 and (same_project or same_generic):
                previous["raw_seconds"] += item["raw_seconds"]
                previous["end"] = max(previous["end"], item["end"])
                previous["task_ids"].extend(item["task_ids"])
                if item["local_description"] not in previous["local_description"]:
                    previous["local_description"] += "; " + item["local_description"]
                previous["assignment_confidence"] = min(
                    previous["assignment_confidence"], item["assignment_confidence"]
                )
                continue
        entries.append(item)

    for entry in entries:
        entry["raw_seconds"] = round(entry["raw_seconds"], 3)
        entry["rounded_seconds"] = _round_seconds(entry["raw_seconds"], increment_minutes)
        entry["final_summary"] = None
        entry["approved"] = False
        if entry["project_id"]:
            entry["project_name"] = project_by_id[entry["project_id"]]["name"]
    return entries


def summary_payload(
    run: Dict[str, Any], include_project_names: bool = True,
    include_apps: bool = False, include_domains: bool = False,
) -> Dict[str, Any]:
    segments = {item["id"]: item for item in run["segments"]}
    tasks = {item["id"]: item for item in run["tasks"]}
    payload_entries = []
    for entry in run["entries"]:
        segment_ids = {
            segment_id for task_id in entry["task_ids"]
            for segment_id in tasks[task_id]["segment_ids"]
        }
        item = {
            "entry_id": entry["id"],
            "duration_seconds": entry["rounded_seconds"],
            "local_description": entry["local_description"],
        }
        if include_project_names:
            item["project"] = entry.get("project_name") or "Unassigned"
        if include_apps:
            item["apps"] = sorted({segments[sid]["app"] for sid in segment_ids})
        if include_domains:
            item["domains"] = sorted({segments[sid]["domain"] for sid in segment_ids if segments[sid].get("domain")})
        payload_entries.append(item)
    return {
        "date": run["range_start"][:10],
        "entries": payload_entries,
        "instructions": {
            "style": "Concise professional timesheet entry",
            "do_not_modify_ids_projects_or_durations": True,
        },
        "privacy": {
            "processing": "local_lm_studio_only",
            "raw_events": "excluded", "window_titles": "excluded",
            "full_urls": "excluded", "apps": "included" if include_apps else "excluded",
            "domains": "included" if include_domains else "excluded",
        },
    }
