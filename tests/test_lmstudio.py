import json

import httpx
import pytest

from app.lmstudio import (
    ClassificationGroup,
    ClassificationResponse,
    LMStudioCancelled,
    LMStudioError,
    LMStudioService,
)


def segment(identifier, duration=60):
    return {
        "id": identifier,
        "start": "2026-01-01T10:00:00+00:00",
        "end": "2026-01-01T10:01:00+00:00",
        "duration_seconds": duration,
        "app": "Code",
        "category": ["Work"],
        "title": "Local title",
        "domain": None,
        "session": 0,
    }


def test_cancel_closes_active_lm_studio_stream_and_client():
    service = LMStudioService("http://lm.test/v1")

    class Closeable:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    response = Closeable()
    client = Closeable()
    service._active_requests["run-one"] = {"response": response, "client": client}

    assert service.cancel("run-one")
    assert response.closed
    assert client.closed
    with pytest.raises(LMStudioCancelled):
        service._raise_if_cancelled("run-one")


def test_model_groups_are_validated_and_missing_segments_become_unassigned(monkeypatch):
    service = LMStudioService("http://lm.test/v1")
    response = ClassificationResponse(
        groups=[
            ClassificationGroup(
                segment_ids=["one"],
                task_label="Implement feature",
                project_hint="TimeLogger",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(
        service,
        "_classify_chunk",
        lambda _segments, _model, repair=False: (
            response
            if not repair and _segments[0]["id"] == "one"
            else ClassificationResponse(groups=[])
        ),
    )
    second = segment("two", 90)
    second["session"] = 1

    selected_model, tasks = service.classify(
        [segment("one", 120), second], "local-model"
    )

    assert selected_model == "local-model"
    assert tasks[0]["duration_seconds"] == 120
    assert tasks[1]["label"] == "Activity in Code"
    assert tasks[1]["duration_seconds"] == 90


def test_malformed_generated_labels_and_project_hints_are_detected():
    broken = ClassificationGroup(
        segment_ids=["S001"],
        task_label="Developing <|reserved_200016|>We have...???………………????",
        project_hint="???",
        confidence=0.9,
    )
    response = ClassificationResponse(groups=[broken])
    assert LMStudioService._invalid_text_groups(response) == {0}

    sanitized = LMStudioService._sanitize_classification_text(response, {0})
    assert sanitized.groups[0].task_label == "Unclassified work"
    assert sanitized.groups[0].project_hint is None
    assert sanitized.groups[0].confidence == 0.25


def test_model_tokens_are_removed_from_otherwise_valid_text():
    assert (
        LMStudioService._clean_generated_text(
            "Developing <|reserved_200016|> TimeLogger"
        )
        == "Developing TimeLogger"
    )


def test_out_of_range_model_confidence_is_normalized():
    high = ClassificationGroup(segment_ids=["S001"], task_label="A", confidence=1.8)
    low = ClassificationGroup(segment_ids=["S001"], task_label="A", confidence=-0.2)
    percent = ClassificationGroup(segment_ids=["S001"], task_label="A", confidence="85%")
    assert high.confidence == 1
    assert low.confidence == 0
    assert percent.confidence == 0.85


def test_short_model_references_are_mapped_back_to_real_ids():
    response = ClassificationResponse(
        groups=[
            ClassificationGroup(
                segment_ids=["s001", "2"], task_label="A", confidence=0.8
            )
        ]
    )
    resolved = LMStudioService._resolve_segment_references(
        response, {"S001": "uuid-one", "S002": "uuid-two"}
    )
    assert resolved.groups[0].segment_ids == ["uuid-one", "uuid-two"]


def test_unknown_short_model_reference_is_rejected():
    response = ClassificationResponse(
        groups=[ClassificationGroup(segment_ids=["S999"], task_label="A", confidence=0.8)]
    )
    with pytest.raises(LMStudioError, match="S999"):
        LMStudioService._resolve_segment_references(response, {"S001": "uuid-one"})


def test_sub_minute_task_is_absorbed_into_nearby_human_sized_entry():
    first = segment("one", 600)
    second = segment("two", 20)
    second["start"] = "2026-01-01T10:01:10+00:00"
    second["end"] = "2026-01-01T10:01:30+00:00"
    tasks = [
        LMStudioService._make_task([first], "Main work", "Project", 0.9, "classified"),
        LMStudioService._make_task([second], "Brief window", None, 0.7, "classified"),
    ]
    consolidated = LMStudioService._consolidate_tasks([first, second], tasks)
    assert len(consolidated) == 1
    assert consolidated[0]["duration_seconds"] == 620
    assert set(consolidated[0]["segment_ids"]) == {"one", "two"}


def test_local_timesheet_summaries_use_lm_studio_and_validate_ids(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "local-model"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "entries": [
                                        {
                                            "entry_id": "E001",
                                            "summary": "Implemented local timeline classification.",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    service = LMStudioService("http://lm.test/v1")
    model, summaries = service.summarize_entries(
        {
            "entries": [
                {
                    "entry_id": "entry-one",
                    "duration_seconds": 1800,
                    "local_description": "Worked on timeline classifier",
                }
            ]
        },
        "local-model",
    )
    assert model == "local-model"
    assert summaries == {
        "entry-one": "Implemented local timeline classification"
    }


def test_detailed_timesheet_summary_is_not_rejected_for_exceeding_task_label_limit(monkeypatch):
    service = LMStudioService("http://lm.test/v1")
    from app.lmstudio import TimesheetSummary, TimesheetSummaryResponse

    detailed = (
        "Implemented recursive Git repository discovery with dependency-directory pruning, "
        "added commit-range filtering and timeline evidence, and covered collection and "
        "segment attachment with automated tests."
    )
    monkeypatch.setattr(
        service,
        "_request_timesheet_summary",
        lambda _request: TimesheetSummaryResponse(
            entries=[TimesheetSummary(entry_id="E001", summary=detailed)]
        ),
    )

    _, summaries = service.summarize_entries(
        {"entries": [{"entry_id": "real-id", "local_description": "Git integration"}]},
        "local-model",
    )

    assert summaries["real-id"] == detailed.rstrip(".")
    assert len(detailed) > 120


def test_malformed_timesheet_summary_uses_local_description_fallback(monkeypatch):
    service = LMStudioService("http://lm.test/v1")
    from app.lmstudio import TimesheetSummary, TimesheetSummaryResponse

    monkeypatch.setattr(
        service,
        "_request_timesheet_summary",
        lambda _request: TimesheetSummaryResponse(
            entries=[
                TimesheetSummary(
                    entry_id="E001",
                    summary="Broken <|reserved_1|>??????????????????",
                )
            ]
        ),
    )
    _, summaries = service.summarize_entries(
        {
            "entries": [
                {
                    "entry_id": "real-id",
                    "local_description": "Implemented ingestion; Added tests; Incidental activity",
                }
            ]
        },
        "local-model",
    )
    assert summaries["real-id"] == "Implemented ingestion; Added tests; Incidental activity"


def test_duplicate_model_assignments_are_repaired_by_keeping_first_group():
    response = ClassificationResponse(
        groups=[
            ClassificationGroup(segment_ids=["one", "two"], task_label="A", confidence=0.8),
            ClassificationGroup(segment_ids=["two", "three"], task_label="B", confidence=0.7),
        ]
    )
    repaired = LMStudioService._deduplicate_assignments(response)
    assert [group.segment_ids for group in repaired.groups] == [["one", "two"], ["three"]]


def test_duplicate_assignments_are_rejected():
    response = ClassificationResponse(
        groups=[
            ClassificationGroup(segment_ids=["one"], task_label="A", confidence=0.8),
            ClassificationGroup(segment_ids=["one"], task_label="B", confidence=0.8),
        ]
    )
    with pytest.raises(LMStudioError, match="more than once"):
        LMStudioService._validate_assignments([segment("one")], response)


def test_unknown_assignments_are_rejected():
    response = ClassificationResponse(
        groups=[ClassificationGroup(segment_ids=["other"], task_label="A", confidence=0.8)]
    )
    with pytest.raises(LMStudioError, match="unknown"):
        LMStudioService._validate_assignments([segment("one")], response)
