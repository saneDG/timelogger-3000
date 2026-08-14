from pathlib import Path

from app.database import RunRepository


def test_cancelled_run_cannot_be_completed_or_failed(tmp_path: Path):
    repository = RunRepository(tmp_path / "cancel.db")
    repository.initialize()
    run = repository.create(
        "2026-01-01T09:00:00+00:00", "2026-01-01T10:00:00+00:00", None
    )

    assert repository.cancel(run["id"])
    repository.mark_running(run["id"], "classifying_locally")
    repository.complete(run["id"], {"event_count": 1, "active_seconds": 60, "categories": [], "apps": []})
    repository.fail(run["id"], "late error")

    saved = repository.get(run["id"])
    assert saved["status"] == "cancelled"
    assert saved["error"] is None
    assert repository.is_cancelled(run["id"])


def test_run_lifecycle(tmp_path: Path):
    repository = RunRepository(tmp_path / "runs.db")
    repository.initialize()
    run = repository.create(
        "2026-01-01T08:00:00+00:00", "2026-01-01T09:00:00+00:00", None
    )

    repository.mark_running(run["id"])
    repository.set_hostname(run["id"], "workstation")
    repository.complete(
        run["id"],
        {
            "event_count": 2,
            "active_seconds": 1800,
            "categories": [{"name": ["Work"], "seconds": 1800}],
            "apps": [{"app": "Code", "seconds": 1800}],
        },
    )

    saved = repository.get(run["id"])
    assert saved is not None
    assert saved["status"] == "completed"
    assert saved["hostname"] == "workstation"
    assert saved["categories"][0]["name"] == ["Work"]
    assert len(repository.list()) == 1
