import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.activitywatch import ActivityWatchError, ActivityWatchService
from app.config import settings
from app.database import RunRepository
from app.git import GitActivityError, attach_to_segments, choose_directory, collect_changes
from app.lmstudio import LMStudioError, LMStudioService, PROMPT_VERSION
from app.timesheet import build_entries, summary_payload


BASE_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", BASE_DIR.parent))
STATIC_DIR = RESOURCE_ROOT / "app" / "static"
repository = RunRepository(settings.database_path)
activitywatch = ActivityWatchService(
    settings.activitywatch_host,
    settings.activitywatch_port,
    settings.title_redaction_patterns,
    settings.redacted_domains,
)
lm_studio = LMStudioService(settings.lm_studio_url)
background_jobs: Set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    yield
    for task in background_jobs:
        task.cancel()


app = FastAPI(title="TimeLogger 3000", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/legal-files", StaticFiles(directory=RESOURCE_ROOT / "licenses"), name="legal-files")
app.mount("/compliance", StaticFiles(directory=RESOURCE_ROOT / "compliance"), name="compliance")


class CreateRunRequest(BaseModel):
    range_start: datetime
    range_end: datetime
    hostname: Optional[str] = None
    model: Optional[str] = None
    git_directory: Optional[str] = Field(default=None, max_length=2000)
    demo: bool = False


class UpdateTaskRequest(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    project_hint: Optional[str] = Field(default=None, max_length=120)


class MergeTasksRequest(BaseModel):
    task_ids: List[str]
    label: Optional[str] = Field(default=None, max_length=160)


class SplitTaskRequest(BaseModel):
    groups: List[List[str]]


class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    customer: Optional[str] = Field(default=None, max_length=120)
    description: str = Field(default="", max_length=1000)
    billing_code: Optional[str] = Field(default=None, max_length=80)
    aliases: List[str] = []
    domains: List[str] = []
    keywords: List[str] = []
    active: bool = True


class GenerateEntriesRequest(BaseModel):
    increment_minutes: int = Field(default=5, ge=1, le=60)


class UpdateEntryRequest(BaseModel):
    project_id: Optional[str] = None
    rounded_seconds: Optional[int] = Field(default=None, ge=60)
    final_summary: Optional[str] = Field(default=None, max_length=500)
    approved: Optional[bool] = None


class SummaryPreviewRequest(BaseModel):
    include_project_names: bool = True
    include_apps: bool = False
    include_domains: bool = False


class GenerateLocalSummaryRequest(SummaryPreviewRequest):
    confirm_generate: bool = False
    model: Optional[str] = None


def _demo_activity_result(start: datetime, end: datetime) -> Dict[str, Any]:
    """Synthetic local-only evidence for the unlinked demo page.

    It deliberately follows the normal segment shape so classification, entry
    construction, and summary generation remain the real application pipeline.
    """
    duration = max(3600, int((end - start).total_seconds()))
    anchor = max(start, end - timedelta(seconds=min(duration, 4 * 3600)))
    samples = [
        (0, 45 * 60, "Code", ["Work", "Development"], "Atlas project: implement the local timesheet generation flow"),
        (65 * 60, 40 * 60, "Code", ["Work", "Development"], "Beacon project: add Git activity evidence and automated tests"),
        (125 * 60, 20 * 60, "Terminal", ["Work", "Development"], "Beacon project: run local integration checks"),
        (165 * 60, 35 * 60, "Code", ["Work", "Development"], "Atlas project: refine output and copy workflow"),
        (220 * 60, 18 * 60, "Firefox", ["Work", "Research"], "Cinder project: review implementation documentation"),
    ]
    segments = []
    for session, (offset, seconds, app, category, title) in enumerate(samples):
        segment_start = anchor + timedelta(seconds=offset)
        if segment_start >= end:
            break
        segment_end = min(segment_start + timedelta(seconds=seconds), end)
        actual_seconds = max(5, (segment_end - segment_start).total_seconds())
        segments.append({
            "id": str(uuid4()), "start": segment_start.isoformat(), "end": segment_end.isoformat(),
            "duration_seconds": actual_seconds, "app": app, "category": category,
            "title": title, "domain": None, "session": session,
        })
    active_seconds = round(sum(item["duration_seconds"] for item in segments), 3)
    return {
        "event_count": len(segments), "active_seconds": active_seconds,
        "categories": [{"name": ["Work", "Development"], "seconds": active_seconds}],
        "apps": [{"app": app, "seconds": round(sum(item["duration_seconds"] for item in segments if item["app"] == app), 3)} for app in sorted({item["app"] for item in segments})],
        "browser_tracking": False, "segments": segments,
    }


def _apply_demo_project_hints(tasks: List[Dict[str, Any]], segments: List[Dict[str, Any]]) -> None:
    """Keep explicitly named mock projects attached to real model task groups."""
    by_id = {segment["id"]: segment for segment in segments}
    for task in tasks:
        evidence = " ".join(by_id[item]["title"] for item in task["segment_ids"])
        matches = [name for name in ("Atlas", "Beacon", "Cinder") if (name + " project:").casefold() in evidence.casefold()]
        if len(matches) == 1:
            task["project_hint"] = matches[0]


def _process_run(run_id: str, request: CreateRunRequest) -> None:
    repository.mark_running(run_id, "reading_activity")
    try:
        if request.demo:
            hostname, result = "demo-workstation", _demo_activity_result(request.range_start, request.range_end)
        else:
            hostname, result = activitywatch.collect(
                request.range_start,
                request.range_end,
                request.hostname or settings.activitywatch_hostname,
            )
        if repository.is_cancelled(run_id):
            return
        repository.set_hostname(run_id, hostname)
        segments = result.pop("segments")
        repository.set_status(run_id, "collecting_git")
        git_changes = [] if request.demo else collect_changes(
            request.git_directory or settings.git_directory,
            request.range_start,
            request.range_end,
        )
        if repository.is_cancelled(run_id):
            return
        attach_to_segments(segments, git_changes)
        repository.set_status(run_id, "classifying_locally")
        model, tasks = lm_studio.classify(
            segments, request.model or settings.lm_studio_model, run_id=run_id
        )
        if request.demo:
            _apply_demo_project_hints(tasks, segments)
        if repository.is_cancelled(run_id):
            return
        repository.set_status(run_id, "saving_results")
        repository.complete_phase2(
            run_id, result, segments, tasks, model, PROMPT_VERSION
        )
    except (ActivityWatchError, GitActivityError, LMStudioError) as exc:
        repository.fail(run_id, str(exc))
    except Exception as exc:
        repository.fail(run_id, "Unexpected processing error: %s" % exc)


async def _run_in_background(run_id: str, request: CreateRunRequest) -> None:
    await asyncio.to_thread(_process_run, run_id, request)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/history", include_in_schema=False)
def history_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "history.html")


@app.get("/licenses", include_in_schema=False)
def licenses_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "licenses.html")


@app.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "demo.html", headers={"X-Robots-Tag": "noindex, nofollow"})


@app.post("/api/git/select-directory")
def select_git_directory():
    try:
        return {"path": choose_directory()}
    except GitActivityError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/api/status")
async def get_status():
    activity_status, lm_status = await asyncio.gather(
        asyncio.to_thread(activitywatch.status), asyncio.to_thread(lm_studio.status)
    )
    activity_status["lm_studio"] = lm_status
    activity_status["activitywatch_mode"] = os.getenv("TIMELOGGER_ACTIVITYWATCH_MODE", "external")
    return activity_status


@app.post("/api/runs", status_code=202)
async def create_run(request: CreateRunRequest):
    if request.range_start.tzinfo is None or request.range_end.tzinfo is None:
        raise HTTPException(status_code=422, detail="The time range must include a timezone.")
    if request.range_start >= request.range_end:
        raise HTTPException(status_code=422, detail="Start time must be before end time.")

    run = repository.create(
        request.range_start.isoformat(), request.range_end.isoformat(), request.hostname
    )
    task = asyncio.create_task(_run_in_background(run["id"], request))
    background_jobs.add(task)
    task.add_done_callback(background_jobs.discard)
    return run


@app.get("/api/runs")
def list_runs(limit: int = Query(default=20, ge=1, le=100)):
    return repository.list(limit)


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    run = repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    repository.cancel(run_id)
    lm_studio.cancel(run_id)
    return repository.get(run_id)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, request: UpdateTaskRequest):
    label = request.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Task label cannot be blank.")
    task = repository.update_task(
        task_id, label, request.project_hint.strip() if request.project_hint else None
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@app.post("/api/tasks/merge")
def merge_tasks(request: MergeTasksRequest):
    if request.label is not None and not request.label.strip():
        raise HTTPException(status_code=422, detail="Task label cannot be blank.")
    try:
        return repository.merge_tasks(
            request.task_ids, request.label.strip() if request.label else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/split")
def split_task(task_id: str, request: SplitTaskRequest):
    try:
        return repository.split_task(task_id, request.groups)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects")
def list_projects(active_only: bool = False):
    return repository.list_projects(active_only)


@app.post("/api/projects", status_code=201)
def create_project(request: ProjectRequest):
    try:
        return repository.create_project(request.model_dump())
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            raise HTTPException(status_code=409, detail="A project with this name already exists.") from exc
        raise


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, request: ProjectRequest):
    project = repository.update_project(project_id, request.model_dump())
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    if not repository.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found.")


def _ensure_demo_projects() -> List[Dict[str, Any]]:
    projects = repository.list_projects(active_only=True)
    existing = {project["name"].casefold() for project in projects}
    for name, keywords in (
        ("Atlas", ["atlas", "timesheet", "output"]),
        ("Beacon", ["beacon", "git", "integration"]),
        ("Cinder", ["cinder", "documentation", "research"]),
    ):
        if name.casefold() not in existing:
            repository.create_project({
                "name": name, "customer": None, "description": "Synthetic demo project.",
                "billing_code": None, "aliases": [], "domains": [], "keywords": keywords,
                "active": True,
            })
    return repository.list_projects(active_only=True)


@app.post("/api/runs/{run_id}/entries")
def generate_entries(run_id: str, request: GenerateEntriesRequest):
    run = repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    projects = _ensure_demo_projects() if run.get("hostname") == "demo-workstation" else repository.list_projects(active_only=True)
    entries = build_entries(
        run["tasks"], run["segments"], projects, request.increment_minutes
    )
    repository.replace_entries(run_id, entries)
    return repository.get(run_id)["entries"]


@app.patch("/api/entries/{entry_id}")
def update_entry(entry_id: str, request: UpdateEntryRequest):
    changes = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        entry = repository.update_entry(entry_id, changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found or no changes supplied.")
    return entry


@app.post("/api/runs/{run_id}/summary-preview")
def preview_summary_payload(run_id: str, request: SummaryPreviewRequest):
    run = repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if not run["entries"]:
        raise HTTPException(status_code=422, detail="Generate timesheet entries first.")
    return summary_payload(run, **request.model_dump())


@app.post("/api/runs/{run_id}/local-summaries")
def generate_local_summaries(run_id: str, request: GenerateLocalSummaryRequest):
    if not request.confirm_generate:
        raise HTTPException(status_code=422, detail="Confirm the reviewed payload before generating.")
    run = repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    payload = summary_payload(
        run, request.include_project_names, request.include_apps, request.include_domains
    )
    try:
        _, summaries = lm_studio.summarize_entries(
            payload, request.model or settings.lm_studio_model, run_id=run_id
        )
        for entry_id, summary in summaries.items():
            repository.update_entry(entry_id, {"final_summary": summary})
        return repository.get(run_id)["entries"]
    except LMStudioError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
