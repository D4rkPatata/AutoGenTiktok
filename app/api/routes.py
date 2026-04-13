from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import GenerateResponse, MusicPreset
from app.services.pipeline import process_generation
from app.services.storage import jobs_dir, music_presets_dir

router = APIRouter()


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


@router.post("/generate", response_model=GenerateResponse)
async def generate_videos(
    clips: list[UploadFile] = File(...),
    versions: int = Form(1),
    style: str = Form("clean_fast"),
    prompt_context: str = Form(""),
    text_fonts: list[str] = Form(...),
    text_effects: list[str] = Form(...),
    text_bold: bool = Form(True),
    music_preset: str | None = Form(None),
    music_file: UploadFile | None = File(None),
) -> GenerateResponse:
    try:
        job_id, final_style, results = await process_generation(
            clips=clips,
            requested_versions=versions,
            style_name=style,
            music_file=music_file,
            music_preset=music_preset,
            prompt_context=prompt_context,
            text_fonts=text_fonts,
            text_effects=text_effects,
            text_bold=text_bold,
        )
    except HTTPException:
        raise
    except Exception as exc:
        # Keep response JSON so the frontend can show a meaningful error.
        raise HTTPException(status_code=500, detail=f"Error interno al generar: {exc}") from exc

    return GenerateResponse(
        job_id=job_id,
        style=final_style,
        requested_versions=versions,
        generated_versions=len(results),
        results=results,
    )


@router.get("/download/{job_id}/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    safe_name = Path(filename).name
    target = jobs_dir() / job_id / "outputs" / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path=target, media_type="video/mp4", filename=safe_name)
