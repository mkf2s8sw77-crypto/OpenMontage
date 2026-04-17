"""Local FastAPI app for the OpenMontage MiniMax Studio."""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from studio_api.storage import (
    build_output_path,
    create_job_id,
    ensure_project_dirs,
    get_job,
    list_assets,
    list_projects,
    load_jobs,
    project_dir,
    resolve_project_file,
    slugify,
    upsert_job,
    utc_now_iso,
)
from tools.audio.minimax_official_music import MiniMaxOfficialMusic
from tools.audio.minimax_official_tts import MiniMaxOfficialTTS
from tools.graphics.minimax_official_image import MiniMaxOfficialImage
from tools.video.minimax_official_video import MiniMaxOfficialVideo


class ProjectCreateRequest(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = None


class TTSRequest(BaseModel):
    project_id: str
    text: str
    model: Optional[str] = None
    voice: Optional[str] = None
    speed: Optional[float] = None
    vol: Optional[float] = None
    pitch: Optional[int] = None
    output_format: str = "mp3"


class ImageRequest(BaseModel):
    project_id: str
    prompt: str
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    image_url: Optional[str] = None
    output_format: str = "png"


class MusicRequest(BaseModel):
    project_id: str
    prompt: str
    model: Optional[str] = None
    duration_seconds: Optional[int] = None


class VideoJobRequest(BaseModel):
    project_id: str
    prompt: str
    operation: str = "text_to_video"
    model: Optional[str] = None
    duration: int = 6
    resolution: str = "1080P"
    first_frame_image: Optional[str] = None
    last_frame_image: Optional[str] = None
    callback_url: Optional[str] = None
    aigc_watermark: bool = False
    prompt_optimizer: bool = True
    poll_interval_seconds: float = Field(default=10, ge=0.1)
    timeout_seconds: float = Field(default=900, ge=1)


app = FastAPI(title="OpenMontage MiniMax Studio API", version="0.1.0")


def error_payload(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def ensure_project(project_id: str) -> str:
    pid = slugify(project_id)
    ensure_project_dirs(pid)
    return pid


def sync_response(project_id: str, category: str, result: Any) -> dict[str, Any]:
    if not result.success:
        raise error_payload("generation_failed", result.error or "Unknown generation error", 500)
    return {
        "project_id": project_id,
        "category": category,
        "artifact": result.data,
        "artifacts": result.artifacts,
    }


def update_job(project_id: str, job: dict[str, Any], **changes: Any) -> dict[str, Any]:
    job.update(changes)
    job["updated_at"] = utc_now_iso()
    return upsert_job(project_id, job)


def run_video_job(project_id: str, job_id: str, payload: dict[str, Any]) -> None:
    job = get_job(project_id, job_id)
    if not job:
        return
    tool = MiniMaxOfficialVideo()
    update_job(project_id, job, status="processing")
    result = tool.execute(payload)
    if result.success:
        update_job(
            project_id,
            job,
            status="success",
            result=result.data,
            artifacts=result.artifacts,
            error=None,
        )
        return
    update_job(project_id, job, status="failed", error=result.error)


@app.get("/api/studio/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/studio/config/status")
def config_status() -> dict[str, Any]:
    return {
        "minimax": {
            "configured": bool(os.environ.get("MINIMAX_API_KEY")),
            "host": os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com"),
        }
    }


@app.get("/api/studio/projects")
def projects() -> dict[str, Any]:
    return {"projects": list_projects()}


@app.post("/api/studio/projects")
def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
    base = request.project_id or request.title or "project"
    project_id = ensure_project(base)
    return {
        "project": {
            "project_id": project_id,
            "path": str(project_dir(project_id)),
        }
    }


@app.get("/api/studio/projects/{project_id}/assets")
def project_assets(project_id: str) -> dict[str, Any]:
    pid = ensure_project(project_id)
    return {"project_id": pid, "assets": list_assets(pid)}


@app.get("/api/studio/projects/{project_id}/files")
def project_file(project_id: str, path: str) -> FileResponse:
    pid = ensure_project(project_id)
    try:
        file_path = resolve_project_file(pid, path)
    except FileNotFoundError:
        raise error_payload("file_not_found", f"File not found: {path}", 404)
    except ValueError as exc:
        raise error_payload("invalid_path", str(exc), 400)
    return FileResponse(file_path)


@app.post("/api/studio/tts")
def generate_tts(request: TTSRequest) -> dict[str, Any]:
    project_id = ensure_project(request.project_id)
    output_path = build_output_path(project_id, "audio", "tts", request.output_format)
    tool = MiniMaxOfficialTTS()
    payload = request.model_dump(exclude_none=True)
    payload["project_id"] = project_id
    payload["output_path"] = str(output_path)
    result = tool.execute(payload)
    return sync_response(project_id, "audio", result)


@app.post("/api/studio/image")
def generate_image(request: ImageRequest) -> dict[str, Any]:
    project_id = ensure_project(request.project_id)
    output_path = build_output_path(project_id, "images", "image", request.output_format)
    tool = MiniMaxOfficialImage()
    payload = request.model_dump(exclude_none=True)
    payload["project_id"] = project_id
    payload["output_path"] = str(output_path)
    result = tool.execute(payload)
    return sync_response(project_id, "images", result)


@app.post("/api/studio/music")
def generate_music(request: MusicRequest) -> dict[str, Any]:
    project_id = ensure_project(request.project_id)
    output_path = build_output_path(project_id, "music", "music", "mp3")
    tool = MiniMaxOfficialMusic()
    payload = request.model_dump(exclude_none=True)
    payload["project_id"] = project_id
    payload["output_path"] = str(output_path)
    result = tool.execute(payload)
    return sync_response(project_id, "music", result)


@app.post("/api/studio/video/jobs")
def create_video_job(request: VideoJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    project_id = ensure_project(request.project_id)
    output_path = build_output_path(project_id, "video", "video", "mp4")
    job_id = create_job_id()
    payload = request.model_dump(exclude_none=True)
    payload["project_id"] = project_id
    payload["output_path"] = str(output_path)
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "status": "queued",
        "type": "video_generation",
        "request": payload,
        "result": None,
        "artifacts": [],
        "error": None,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    upsert_job(project_id, job)
    background_tasks.add_task(run_video_job, project_id, job_id, payload)
    return {"job": job}


@app.get("/api/studio/jobs")
def list_jobs(project_id: Optional[str] = None) -> dict[str, Any]:
    if project_id:
        pid = ensure_project(project_id)
        return {"jobs": load_jobs(pid)}
    jobs: list[dict[str, Any]] = []
    for project in list_projects():
        jobs.extend(load_jobs(project["project_id"]))
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"jobs": jobs}


@app.get("/api/studio/jobs/{job_id}")
def get_job_detail(job_id: str, project_id: str) -> dict[str, Any]:
    pid = ensure_project(project_id)
    job = get_job(pid, job_id)
    if not job:
        raise error_payload("job_not_found", f"Job {job_id} not found", 404)
    return {"job": job}
