import os
import subprocess
from datetime import datetime, timedelta, timezone

from app.git import attach_to_segments, choose_directory, collect_changes


def git(path, *args, env=None):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, env=env)


def test_native_picker_returns_selected_path(monkeypatch):
    class Result:
        returncode = 0
        stdout = "/Users/local/Developer/\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())

    assert choose_directory() == "/Users/local/Developer"


def test_collects_commits_in_selected_range(tmp_path):
    repository = tmp_path / "product"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Local User")
    git(repository, "config", "user.email", "local@example.test")
    (repository / "feature.txt").write_text("local change")
    git(repository, "add", "feature.txt")
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = "2026-01-01T10:30:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2026-01-01T10:30:00+00:00"
    git(repository, "commit", "-m", "Implement local history", env=env)

    changes = collect_changes(
        str(tmp_path),
        datetime.fromisoformat("2026-01-01T10:00:00+00:00"),
        datetime.fromisoformat("2026-01-01T11:00:00+00:00"),
    )

    assert len(changes) == 1
    assert changes[0]["repository"] == "product"
    assert changes[0]["subject"] == "Implement local history"
    assert changes[0]["files_changed"] == 1


def test_collects_staged_unstaged_and_untracked_working_tree_changes(tmp_path):
    repository = tmp_path / "product"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Local User")
    git(repository, "config", "user.email", "local@example.test")
    (repository / "staged.py").write_text("initial")
    (repository / "unstaged.py").write_text("initial")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Initial files")

    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    (repository / "staged.py").write_text("staged metadata only")
    git(repository, "add", "staged.py")
    (repository / "unstaged.py").write_text("unstaged metadata only")
    (repository / "new.py").write_text("untracked metadata only")
    end = datetime.now(timezone.utc) + timedelta(minutes=1)

    working = [
        change for change in collect_changes(str(tmp_path), start, end)
        if change.get("kind") == "working_tree"
    ]

    by_path = {change["path"]: change for change in working}
    assert by_path["staged.py"]["states"] == ["staged"]
    assert by_path["unstaged.py"]["states"] == ["unstaged"]
    assert by_path["new.py"]["states"] == ["untracked"]
    assert all("content" not in change and "diff" not in change for change in working)


def test_attaches_commit_to_nearest_segment_without_changing_duration():
    segments = [{
        "id": "one", "start": "2026-01-01T10:00:00+00:00",
        "end": "2026-01-01T11:00:00+00:00", "duration_seconds": 1200,
        "title": "Editor", "app": "Code", "category": ["Work"], "domain": None,
        "session": 0,
    }]
    changes = [{"repository": "product", "timestamp": "2026-01-01T10:30:00+00:00", "subject": "Implement local history", "files_changed": 2}]

    attach_to_segments(segments, changes)

    assert "Git product commit: Implement local history (2 files)" in segments[0]["title"]
    assert segments[0]["duration_seconds"] == 1200


def test_attaches_working_tree_file_metadata_to_segment():
    segments = [{
        "id": "one", "start": "2026-01-01T10:00:00+00:00",
        "end": "2026-01-01T11:00:00+00:00", "duration_seconds": 1200,
        "title": "Editor", "app": "Code", "category": ["Work"], "domain": None,
        "session": 0,
    }]
    changes = [{
        "repository": "product", "kind": "working_tree",
        "timestamp": "2026-01-01T10:30:00+00:00", "path": "app/git.py",
        "states": ["staged"],
    }]

    attach_to_segments(segments, changes)

    assert "Git product working tree: app/git.py (staged)" in segments[0]["title"]
