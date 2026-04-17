"""Project and job persistence helpers for the local MiniMax Studio API."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = REPO_ROOT / "projects"
JOB_FILENAME = "minimax_studio_jobs.json"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
    return cleaned.strip("-") or "project"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job_id() -> str:
    return uuid4().hex[:12]


def project_dir(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id


def ensure_project_dirs(project_id: str) -> Path:
    root = project_dir(project_id)
    for relative in (
        "assets/audio",
        "assets/images",
        "assets/video",
        "assets/music",
        "artifacts",
        "renders",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    return root


def list_projects() -> list[dict[str, Any]]:
    if not PROJECTS_ROOT.exists():
        return []
    projects: list[dict[str, Any]] = []
    for child in sorted(PROJECTS_ROOT.iterdir()):
        if not child.is_dir():
            continue
        jobs = load_jobs(child.name)
        projects.append(
            {
                "project_id": child.name,
                "path": str(child),
                "job_count": len(jobs),
            }
        )
    return projects


def jobs_path(project_id: str) -> Path:
    return ensure_project_dirs(project_id) / "artifacts" / JOB_FILENAME


def load_jobs(project_id: str) -> list[dict[str, Any]]:
    path = jobs_path(project_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_jobs(project_id: str, jobs: list[dict[str, Any]]) -> None:
    path = jobs_path(project_id)
    path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_job(project_id: str, job: dict[str, Any]) -> dict[str, Any]:
    jobs = load_jobs(project_id)
    for index, existing in enumerate(jobs):
        if existing.get("job_id") == job.get("job_id"):
            jobs[index] = job
            save_jobs(project_id, jobs)
            return job
    jobs.append(job)
    save_jobs(project_id, jobs)
    return job


def get_job(project_id: str, job_id: str) -> Optional[dict[str, Any]]:
    for job in load_jobs(project_id):
        if job.get("job_id") == job_id:
            return job
    return None


def build_output_path(project_id: str, category: str, stem: str, extension: str) -> Path:
    root = ensure_project_dirs(project_id)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{stem}-{timestamp}.{extension.lstrip('.')}"
    category_map = {
        "audio": root / "assets" / "audio",
        "images": root / "assets" / "images",
        "video": root / "assets" / "video",
        "music": root / "assets" / "music",
    }
    output_dir = category_map[category]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def list_assets(project_id: str) -> list[dict[str, Any]]:
    root = ensure_project_dirs(project_id) / "assets"
    assets: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir(project_id)).as_posix()
        category = rel.split("/", 2)[1] if rel.startswith("assets/") else "unknown"
        assets.append(
            {
                "path": rel,
                "category": category,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
            }
        )
    return assets


def resolve_project_file(project_id: str, relative_path: str) -> Path:
    base = ensure_project_dirs(project_id)
    candidate = (base / relative_path).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError("Requested file is outside the project directory") from exc
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate
