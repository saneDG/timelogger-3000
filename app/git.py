import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitActivityError(RuntimeError):
    pass


def choose_directory() -> Optional[str]:
    """Open the native macOS Finder folder chooser and return its POSIX path."""
    try:
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select a directory containing Git repositories")'],
            capture_output=True, text=True, timeout=300, check=False,
        )
    except FileNotFoundError as exc:
        raise GitActivityError("The native directory picker is only available on macOS.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitActivityError("The directory picker timed out.") from exc
    if result.returncode:
        if "canceled" in result.stderr.casefold() or "cancelled" in result.stderr.casefold():
            return None
        raise GitActivityError(result.stderr.strip() or "Could not open the directory picker.")
    return result.stdout.strip().rstrip("/") or None


def _run_git(repository: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *args], capture_output=True, text=True,
            timeout=12, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitActivityError("Could not inspect %s: %s" % (repository, exc)) from exc
    if result.returncode:
        raise GitActivityError(result.stderr.strip() or "Git command failed for %s." % repository)
    return result.stdout


def _working_tree_changes(
    repository: Path, root: Path, start: datetime, end: datetime
) -> List[Dict[str, Any]]:
    status = _run_git(
        repository, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).split("\0")
    try:
        index_path = Path(_run_git(repository, "rev-parse", "--git-path", "index").strip())
        if not index_path.is_absolute():
            index_path = repository / index_path
        index_timestamp = index_path.stat().st_mtime
    except (GitActivityError, OSError):
        index_timestamp = 0

    changes: List[Dict[str, Any]] = []
    position = 0
    while position < len(status):
        record = status[position]
        position += 1
        if len(record) < 4:
            continue
        code, relative_path = record[:2], record[3:]
        # Porcelain emits an additional NUL-delimited source path for renames/copies.
        if code[0] in {"R", "C"} and position < len(status):
            position += 1
        staged = code[0] not in {" ", "?", "!"}
        unstaged = code[1] not in {" ", "?", "!"}
        untracked = code == "??"
        path = repository / relative_path
        try:
            working_timestamp = path.stat().st_mtime
        except OSError:
            try:
                working_timestamp = path.parent.stat().st_mtime if "D" in code else 0
            except OSError:
                working_timestamp = 0
        timestamp_value = max(
            working_timestamp if unstaged or untracked else 0,
            index_timestamp if staged else 0,
        )
        if not timestamp_value:
            continue
        timestamp = datetime.fromtimestamp(timestamp_value, tz=start.tzinfo)
        if not start <= timestamp <= end:
            continue
        states = []
        if staged:
            states.append("staged")
        if unstaged:
            states.append("unstaged")
        if untracked:
            states.append("untracked")
        if "D" in code:
            states.append("deleted")
        if "R" in code:
            states.append("renamed")
        changes.append(
            {
                "repository": str(repository.relative_to(root) or "."),
                "kind": "working_tree",
                "timestamp": timestamp.isoformat(),
                "path": relative_path,
                "states": states,
            }
        )
    return changes


def collect_changes(root: Optional[str], start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """Return commit and current working-tree metadata for repositories below root.

    Working-tree changes are attributed using file/index modification times. Git
    does not retain historical uncommitted snapshots. Diffs and file contents are
    deliberately never read.
    """
    if not root:
        return []
    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise GitActivityError("Git directory does not exist: %s" % directory)
    repositories = []
    ignored = {"node_modules", ".venv", "venv", "dist", "build", ".cache", ".tox", ".mypy_cache", ".pytest_cache", "vendor"}
    for current_root, directories, _ in os.walk(directory):
        current = Path(current_root)
        if ".git" in directories:
            repositories.append(current)
            # A repository may contain submodules, but recursively scanning its
            # dependencies and worktrees is much more expensive than useful here.
            directories[:] = []
            continue
        directories[:] = [name for name in directories if name not in ignored and not name.startswith(".")]
    repositories.sort()
    changes: List[Dict[str, Any]] = []
    for repository in repositories:
        try:
            lines = _run_git(
                repository, "log", "--format=%H%x1f%h%x1f%cI%x1f%s", "--numstat",
                "--since=" + start.isoformat(), "--until=" + end.isoformat(),
            ).splitlines()
        except GitActivityError:
            continue
        current: Optional[Dict[str, Any]] = None
        for line in lines:
            fields = line.split("\x1f")
            if len(fields) == 4:
                if current:
                    changes.append(current)
                current = {"repository": str(repository.relative_to(directory) or "."), "hash": fields[1], "timestamp": fields[2], "subject": fields[3], "files_changed": 0}
            elif current and line.strip():
                parts = line.split("\t")
                if len(parts) == 3:
                    current["files_changed"] += 1
        if current:
            changes.append(current)
        try:
            changes.extend(_working_tree_changes(repository, directory, start, end))
        except GitActivityError:
            continue
    return sorted(changes, key=lambda item: item["timestamp"])


def attach_to_segments(segments: List[Dict[str, Any]], changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add commit metadata as local-only evidence on the nearest timeline segment."""
    if not segments or not changes:
        return segments
    for change in changes:
        timestamp = datetime.fromisoformat(change["timestamp"].replace("Z", "+00:00"))
        candidates = []
        for segment in segments:
            start = datetime.fromisoformat(segment["start"])
            end = datetime.fromisoformat(segment["end"])
            distance = 0 if start <= timestamp <= end else min(abs((timestamp - start).total_seconds()), abs((timestamp - end).total_seconds()))
            candidates.append((distance, segment))
        distance, segment = min(candidates, key=lambda item: item[0])
        if distance <= 7200:
            if change.get("kind") == "working_tree":
                evidence = "Git %s working tree: %s (%s)" % (
                    change["repository"], change["path"], ", ".join(change["states"])
                )
            else:
                evidence = "Git %s commit: %s (%s files)" % (
                    change["repository"], change["subject"], change["files_changed"]
                )
            segment["title"] = " | ".join(filter(None, [segment.get("title"), evidence]))
    return segments
