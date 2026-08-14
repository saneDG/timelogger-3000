from pathlib import Path

from app.database import RunRepository


def test_phase2_results_store_sanitized_segments_and_edit_tasks(tmp_path: Path):
    repository = RunRepository(tmp_path / "phase2.db")
    repository.initialize()
    run = repository.create("2026-01-01T08:00:00+00:00", "2026-01-01T09:00:00+00:00", "Mac")
    segments = [
        {
            "id": "s1", "start": "2026-01-01T08:00:00+00:00",
            "end": "2026-01-01T08:10:00+00:00", "duration_seconds": 600,
            "app": "Code", "category": ["Work"], "domain": "github.com",
            "title": "Secret repository name", "session": 0,
        },
        {
            "id": "s2", "start": "2026-01-01T08:10:00+00:00",
            "end": "2026-01-01T08:15:00+00:00", "duration_seconds": 300,
            "app": "Code", "category": ["Work"], "domain": None,
            "title": "Secret filename", "session": 0,
        },
    ]
    tasks = [
        {
            "id": "t1", "label": "First", "project_hint": None, "confidence": 0.9,
            "duration_seconds": 600, "start": segments[0]["start"], "end": segments[0]["end"],
            "status": "classified", "segment_ids": ["s1"],
        },
        {
            "id": "t2", "label": "Second", "project_hint": None, "confidence": 0.8,
            "duration_seconds": 300, "start": segments[1]["start"], "end": segments[1]["end"],
            "status": "classified", "segment_ids": ["s2"],
        },
    ]
    result = {
        "event_count": 2, "active_seconds": 900, "categories": [], "apps": [],
        "browser_tracking": True,
    }

    repository.complete_phase2(run["id"], result, segments, tasks, "local-model", "v1")
    saved = repository.get(run["id"])

    assert saved is not None
    assert saved["model"] == "local-model"
    assert "title" not in saved["segments"][0]
    assert saved["segments"][0]["domain"] == "github.com"
    assert saved["work_sessions"][0]["start"] == segments[0]["start"]
    assert saved["work_sessions"][0]["end"] == segments[1]["end"]
    assert saved["work_sessions"][0]["active_seconds"] == 900

    edited = repository.update_task("t1", "Edited label", "Project")
    assert edited["label"] == "Edited label"
    merged = repository.merge_tasks(["t1", "t2"], "Combined")
    assert merged["duration_seconds"] == 900
    assert set(merged["segment_ids"]) == {"s1", "s2"}

    split = repository.split_task(merged["id"], [["s1"], ["s2"]])
    assert [task["duration_seconds"] for task in split] == [600, 300]
