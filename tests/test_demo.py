from datetime import datetime, timedelta, timezone

from app.main import _apply_demo_project_hints, _demo_activity_result


def test_demo_activity_result_uses_synthetic_timeline_evidence():
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    result = _demo_activity_result(start, start + timedelta(hours=4))

    assert result["event_count"] == len(result["segments"])
    assert result["active_seconds"] > 0
    assert {segment["app"] for segment in result["segments"]} >= {"Code", "Terminal"}
    assert all(segment["start"] >= start.isoformat() for segment in result["segments"])
    assert all("title" in segment and segment["title"] for segment in result["segments"])
    assert {"Atlas", "Beacon", "Cinder"} <= {segment["title"].split(" project:")[0] for segment in result["segments"]}


def test_demo_project_hints_are_preserved_after_model_classification():
    result = _demo_activity_result(
        datetime(2026, 1, 1, 9, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 13, tzinfo=timezone.utc),
    )
    tasks = [
        {"segment_ids": [segment["id"]], "project_hint": None}
        for segment in result["segments"]
    ]

    _apply_demo_project_hints(tasks, result["segments"])

    assert {task["project_hint"] for task in tasks} == {"Atlas", "Beacon", "Cinder"}
