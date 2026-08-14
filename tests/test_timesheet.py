from app.timesheet import assign_project, build_entries, summary_payload


def test_project_assignment_and_same_project_consolidation():
    segments = [
        {"id": "s1", "app": "Code", "domain": None, "category": ["Work"]},
        {"id": "s2", "app": "Firefox", "domain": "github.com", "category": ["Work"]},
    ]
    tasks = [
        {"id": "t1", "label": "Implement TimeLogger API", "project_hint": "TimeLogger",
         "start": "2026-01-01T10:00:00+00:00", "end": "2026-01-01T10:20:00+00:00",
         "duration_seconds": 1200, "segment_ids": ["s1"]},
        {"id": "t2", "label": "Test TimeLogger", "project_hint": "TimeLogger",
         "start": "2026-01-01T10:21:00+00:00", "end": "2026-01-01T10:31:00+00:00",
         "duration_seconds": 600, "segment_ids": ["s2"]},
    ]
    projects = [{"id": "p1", "name": "TimeLogger 3000", "aliases": ["TimeLogger"],
                 "domains": [], "keywords": ["API"]}]
    entries = build_entries(tasks, segments, projects, 5)
    assert len(entries) == 1
    assert entries[0]["project_id"] == "p1"
    assert entries[0]["raw_seconds"] == 1800
    assert entries[0]["rounded_seconds"] == 1800
    assert entries[0]["task_ids"] == ["t1", "t2"]


def test_summary_payload_omits_sensitive_context_by_default():
    run = {
        "range_start": "2026-01-01T08:00:00+00:00",
        "entries": [{"id": "e1", "project_name": "Project", "rounded_seconds": 1800,
                     "local_description": "Implemented API", "task_ids": ["t1"]}],
        "tasks": [{"id": "t1", "segment_ids": ["s1"]}],
        "segments": [{"id": "s1", "app": "Code", "domain": "private.example"}],
    }
    payload = summary_payload(run)
    entry = payload["entries"][0]
    assert entry["project"] == "Project"
    assert "apps" not in entry
    assert "domains" not in entry
    assert payload["privacy"]["processing"] == "local_lm_studio_only"
    assert payload["privacy"]["window_titles"] == "excluded"
