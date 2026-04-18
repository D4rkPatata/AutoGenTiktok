import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings


def base_dir() -> Path:
    return settings.workspace_dir


def jobs_dir() -> Path:
    return base_dir() / settings.jobs_dir_name


def music_presets_dir() -> Path:
    return base_dir() / settings.music_presets_dir_name


def ensure_base_dirs() -> None:
    jobs_dir().mkdir(parents=True, exist_ok=True)
    music_presets_dir().mkdir(parents=True, exist_ok=True)


def create_job_dirs(job_id: str | None = None) -> tuple[str, Path, Path, Path]:
    job_id = job_id or uuid4().hex[:12]
    root = jobs_dir() / job_id
    inputs = root / "inputs"
    outputs = root / "outputs"
    work = root / "work"
    for folder in (inputs, outputs, work):
        folder.mkdir(parents=True, exist_ok=True)
    return job_id, inputs, outputs, work


def cleanup_job(job_id: str) -> None:
    path = jobs_dir() / job_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def cleanup_old_jobs() -> None:
    ttl = timedelta(hours=settings.cleanup_after_hours)
    now = datetime.now(timezone.utc)

    for job_folder in jobs_dir().glob("*"):
        if not job_folder.is_dir():
            continue
        mtime = datetime.fromtimestamp(job_folder.stat().st_mtime, tz=timezone.utc)
        if now - mtime > ttl:
            shutil.rmtree(job_folder, ignore_errors=True)
