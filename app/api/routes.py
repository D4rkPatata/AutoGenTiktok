import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.schemas import (
    GenerateResponse,
    MusicPreset,
    TiktokConnectionStatus,
    TiktokDraftRequest,
    TiktokDraftResponse,
    ZipRequest,
)
from app.services.pipeline import process_generation
from app.services.drive import (
    DriveIntegrationError,
    list_drive_folder_videos,
    list_folder_contents_oauth,
    list_subfolders_oauth,
)
from app.services.tiktok import TiktokIntegrationError, get_connection_status, send_drafts
from app.services.storage import jobs_dir, music_presets_dir

router = APIRouter()

# ── Background job tracking ───────────────────────────────────────────────────
_jobs: dict[str, dict] = {}


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/music-presets", response_model=list[MusicPreset])
def list_music_presets() -> list[MusicPreset]:
    allowed = {".mp3", ".wav", ".m4a", ".aac"}
    presets: list[MusicPreset] = []

    for file in sorted(music_presets_dir().glob("*")):
        if file.is_file() and file.suffix.lower() in allowed:
            presets.append(MusicPreset(name=file.stem.replace("_", " "), filename=file.name))
    return presets


@router.get("/drive/folders")
def list_drive_folders(request: Request, parent: str = Query("root")) -> dict:
    access_token = request.session.get("google_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Debes iniciar sesion con Google para navegar Drive")
    try:
        folders = list_subfolders_oauth(parent_id=parent, access_token=access_token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando carpetas de Drive: {exc}") from exc
    return {"folders": folders}


@router.get("/drive/contents")
def drive_contents(request: Request, parent: str = Query("root")) -> dict:
    """Returns both subfolders and video files inside parent — requires OAuth login."""
    access_token = request.session.get("google_access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Debes iniciar sesion con Google para navegar Drive")
    try:
        contents = list_folder_contents_oauth(parent_id=parent, access_token=access_token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando Drive: {exc}") from exc
    return contents


@router.get("/drive/preview")
def preview_drive_folder(request: Request, folder: str = Query("", min_length=1)) -> dict:
    access_token = request.session.get("google_access_token")
    try:
        files = list_drive_folder_videos(folder, access_token=access_token)
    except DriveIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error consultando Drive: {exc}") from exc

    allowed_ext = {".mp4", ".mov"}
    videos = []
    for item in files:
        name = str(item.get("name") or "")
        ext = Path(name).suffix.lower()
        videos.append(
            {
                "id": item.get("id"),
                "name": name,
                "size": item.get("size"),
                "is_supported": ext in allowed_ext,
            }
        )

    return {"count": len(videos), "videos": videos}


@router.post("/generate")
async def generate_videos(
    request: Request,
    background_tasks: BackgroundTasks,
    clips: list[UploadFile] | None = File(None),
    versions: int = Form(1),
    style: str = Form("clean_fast"),
    prompt_context: str = Form(""),
    text_fonts: list[str] = Form(...),
    text_effects: list[str] = Form(...),
    text_bold: bool = Form(True),
    drive_folder_id: str = Form(""),
    drive_file_ids: str = Form(""),
    centered_text: str = Form(""),
    music_preset: str | None = Form(None),
    music_file: UploadFile | None = File(None),
    text_mode: str = Form("two_lines"),
    narrator: bool = Form(False),
) -> JSONResponse:
    import json as _json

    oauth_token: str | None = request.session.get("google_access_token")
    parsed_file_ids: list[str] = []
    if drive_file_ids.strip():
        try:
            parsed_file_ids = _json.loads(drive_file_ids)
        except Exception:
            pass

    # Pre-read all upload content before handing off to background task
    # (UploadFile streams are only valid during the request lifecycle)
    read_clips: list[tuple[str, bytes]] = []
    if clips:
        for upload in clips:
            data = await upload.read()
            read_clips.append((upload.filename or "", data))

    read_music: tuple[str, bytes] | None = None
    if music_file and music_file.filename:
        data = await music_file.read()
        read_music = (music_file.filename, data)

    job_id = uuid4().hex[:12]
    _jobs[job_id] = {"status": "processing", "step": "Iniciando...", "progress": 0.0}

    async def _run() -> None:
        def _on_progress(step: str, pct: float) -> None:
            _jobs[job_id]["step"] = step
            _jobs[job_id]["progress"] = pct

        try:
            import starlette.datastructures as _ds

            # Rebuild UploadFile-like objects from pre-read bytes
            rebuilt_clips: list[UploadFile] = []
            for fname, data in read_clips:
                spooled = _ds.UploadFile(file=BytesIO(data), filename=fname)
                rebuilt_clips.append(spooled)

            rebuilt_music: UploadFile | None = None
            if read_music:
                fname, data = read_music
                rebuilt_music = _ds.UploadFile(file=BytesIO(data), filename=fname)

            _, final_style, results = await process_generation(
                clips=rebuilt_clips,
                requested_versions=versions,
                style_name=style,
                music_file=rebuilt_music,
                music_preset=music_preset,
                prompt_context=prompt_context,
                text_fonts=text_fonts,
                text_effects=text_effects,
                text_bold=text_bold,
                drive_folder_id=drive_folder_id,
                drive_file_ids=parsed_file_ids,
                centered_text=centered_text,
                text_mode=text_mode,
                narrator=narrator,
                oauth_token=oauth_token,
                job_id=job_id,
                progress_callback=_on_progress,
            )
            _jobs[job_id] = {
                "status": "done",
                "step": "Listo",
                "progress": 1.0,
                "result": GenerateResponse(
                    job_id=job_id,
                    style=final_style,
                    requested_versions=versions,
                    generated_versions=len(results),
                    results=results,
                ).model_dump(),
            }
        except Exception as exc:
            _jobs[job_id] = {"status": "error", "step": "Error", "progress": 0.0, "error": str(exc)}

    background_tasks.add_task(_run)
    return JSONResponse({"job_id": job_id, "status": "processing"})


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


@router.get("/download/{job_id}/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    safe_name = Path(filename).name
    target = jobs_dir() / job_id / "outputs" / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path=target, media_type="video/mp4", filename=safe_name)


@router.delete("/videos/{job_id}/{filename}")
def delete_video(job_id: str, filename: str) -> dict:
    safe_name = Path(filename).name
    target = jobs_dir() / job_id / "outputs" / safe_name
    if target.exists():
        target.unlink()
    return {"deleted": True}


def _selected_video_paths(job_id: str, requested_filenames: list[str]) -> list[Path]:
    outputs_dir = jobs_dir() / job_id / "outputs"
    if not outputs_dir.exists():
        raise HTTPException(status_code=404, detail="Job no encontrado")

    available = {path.name: path for path in outputs_dir.glob("*.mp4") if path.is_file()}
    if not available:
        raise HTTPException(status_code=404, detail="No hay videos para este job")

    if not requested_filenames:
        return sorted(available.values())

    selected: list[Path] = []
    for raw_name in requested_filenames:
        safe_name = Path(raw_name).name
        candidate = available.get(safe_name)
        if candidate is None:
            raise HTTPException(status_code=400, detail=f"Video no encontrado en el job: {safe_name}")
        selected.append(candidate)
    return selected


@router.post("/download-zip/{job_id}")
def download_zip(job_id: str, payload: ZipRequest) -> FileResponse:
    selected_paths = _selected_video_paths(job_id=job_id, requested_filenames=payload.filenames)
    zip_name = f"{job_id}_videos.zip"
    zip_path = jobs_dir() / job_id / "outputs" / zip_name

    with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED) as archive:
        for video_path in selected_paths:
            archive.write(video_path, arcname=video_path.name)

    return FileResponse(path=zip_path, media_type="application/zip", filename=zip_name)


@router.get("/tiktok/status", response_model=TiktokConnectionStatus)
def tiktok_status(request: Request) -> TiktokConnectionStatus:
    session_token = request.session.get("tiktok_access_token")
    session_open_id = request.session.get("tiktok_user", {}).get("open_id")
    connected, message = get_connection_status(session_token=session_token, session_open_id=session_open_id)
    return TiktokConnectionStatus(connected=connected, message=message)


@router.post("/tiktok/drafts/{job_id}", response_model=TiktokDraftResponse)
def send_tiktok_drafts(request: Request, job_id: str, payload: TiktokDraftRequest) -> TiktokDraftResponse:
    session_token = request.session.get("tiktok_access_token")
    session_open_id = request.session.get("tiktok_user", {}).get("open_id")
    selected_paths = _selected_video_paths(job_id=job_id, requested_filenames=payload.filenames)
    try:
        results = send_drafts(selected_paths, access_token=session_token, open_id=session_open_id)
    except TiktokIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error enviando drafts a TikTok: {exc}") from exc

    sent = len([item for item in results if item.ok])
    return TiktokDraftResponse(sent=sent, attempted=len(results), results=results)
