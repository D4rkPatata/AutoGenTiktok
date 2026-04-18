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
from app.config import settings

router = APIRouter()

# ── Background job tracking ───────────────────────────────────────────────────
_jobs: dict[str, dict] = {}


@router.get("/health")
def health() -> dict:
    return {"ok": True}


_JAMENDO_ALLOWED_ORDERS = {"popularity_week", "popularity_month", "popularity_total", "releasedate"}


def _jamendo_tracks(params: dict) -> list[dict]:
    from urllib.request import urlopen
    from urllib.parse import urlencode
    import json as _json

    if not settings.jamendo_client_id:
        raise HTTPException(status_code=503, detail="Librería no configurada — agrega JAMENDO_CLIENT_ID a tu .env (gratis en developer.jamendo.com)")

    params.setdefault("client_id", settings.jamendo_client_id)
    params.setdefault("format", "json")
    params.setdefault("audioformat", "mp32")
    params.setdefault("imagesize", "200")

    url = f"https://api.jamendo.com/v3.0/tracks/?{urlencode(params)}"
    try:
        with urlopen(url, timeout=10) as resp:  # nosec B310
            data = _json.loads(resp.read())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error consultando Jamendo: {exc}") from exc

    return [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "artist": t.get("artist_name"),
            "duration": t.get("duration"),
            "audio_url": t.get("audio"),
            "image_url": t.get("image"),
        }
        for t in data.get("results", [])
    ]


@router.get("/music/featured")
def featured_music(limit: int = Query(15), order: str = Query("popularity_week"), genre: str = Query("")) -> dict:
    if order not in _JAMENDO_ALLOWED_ORDERS:
        order = "popularity_week"
    params: dict = {"limit": limit, "order": order}
    if genre.strip():
        params["tags"] = genre.strip()
    tracks = _jamendo_tracks(params)
    return {"tracks": tracks}


@router.get("/music/search")
def search_music(q: str = Query(""), limit: int = Query(15), order: str = Query("popularity_week"), genre: str = Query("")) -> dict:
    if order not in _JAMENDO_ALLOWED_ORDERS:
        order = "popularity_week"
    params: dict = {"limit": limit, "order": order}
    if q.strip():
        params["namesearch"] = q.strip()
    if genre.strip():
        params["tags"] = genre.strip()
    tracks = _jamendo_tracks(params)
    return {"tracks": tracks}


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
    music_url: str = Form(""),
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

    def _on_progress(step: str, pct: float) -> None:
        _jobs[job_id]["step"] = step
        _jobs[job_id]["progress"] = pct

    def _run_in_thread() -> None:
        """Runs in a worker thread so blocking subprocess calls don't starve the event loop."""
        import starlette.datastructures as _ds

        rebuilt_clips = [_ds.UploadFile(file=BytesIO(data), filename=fname) for fname, data in read_clips]
        rebuilt_music = _ds.UploadFile(file=BytesIO(read_music[1]), filename=read_music[0]) if read_music else None

        async def _core() -> tuple[str, list]:
            _, final_style, results = await process_generation(
                clips=rebuilt_clips,
                requested_versions=versions,
                style_name=style,
                music_file=rebuilt_music,
                music_preset=music_preset,
                music_url=music_url or None,
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
            return final_style, results

        try:
            final_style, results = asyncio.run(_core())
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

    background_tasks.add_task(_run_in_thread)
    return JSONResponse({"job_id": job_id, "status": "processing"})


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


@router.post("/tiktok/send-test")
def tiktok_send_test(request: Request) -> dict:
    """Generates a tiny 3-second test video and sends it directly to TikTok — for debugging auth."""
    import subprocess, tempfile
    session_token = request.session.get("tiktok_access_token")
    session_open_id = request.session.get("tiktok_user", {}).get("open_id")
    effective_token = session_token or settings.tiktok_access_token
    effective_open_id = session_open_id or settings.tiktok_open_id
    if not effective_token:
        raise HTTPException(status_code=401, detail="No hay token de TikTok en sesión")

    # Generate a tiny black 1080x1920 video
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        settings.ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=3",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(tmp_path),
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)  # nosec B603
    if not tmp_path.exists() or tmp_path.stat().st_size < 1000:
        raise HTTPException(status_code=500, detail="FFmpeg no pudo generar video de prueba")

    from app.services.tiktok import send_drafts, TiktokIntegrationError
    try:
        results = send_drafts([tmp_path], access_token=session_token, open_id=session_open_id)
    except TiktokIntegrationError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        tmp_path.unlink(missing_ok=True)

    r = results[0]
    return {"ok": r.ok, "filename": r.filename, "message": r.message,
            "token_preview": effective_token[:20] + "...", "open_id": effective_open_id}


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
    import logging; logging.getLogger("tiktok").warning("TOKEN=%s... OPEN_ID=%s", (session_token or "")[:20], session_open_id)
    selected_paths = _selected_video_paths(job_id=job_id, requested_filenames=payload.filenames)
    captions = [payload.captions.get(p.name, p.stem) for p in selected_paths]
    public_urls: list[str] | None = None
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
        public_urls = [f"{base}/api/download/{job_id}/{p.name}" for p in selected_paths]
    try:
        results = send_drafts(selected_paths, access_token=session_token, open_id=session_open_id, public_urls=public_urls, captions=captions)
    except TiktokIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error enviando drafts a TikTok: {exc}") from exc

    sent = len([item for item in results if item.ok])
    return TiktokDraftResponse(sent=sent, attempted=len(results), results=results)
