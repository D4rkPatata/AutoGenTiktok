from __future__ import annotations

import shutil
import random
import subprocess
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.schemas import GeneratedVideo
from app.services.analyzer import analyze_clips
from app.services.captioner import generate_text_pack
from app.services.editor import pick_style, render_variant
from app.services.drive import DriveIntegrationError, download_drive_videos, download_drive_files_by_id
from app.services.probe import MediaInfo, probe_media
from app.services.storage import create_job_dirs, music_presets_dir

ALLOWED_VIDEO_EXTS = {".mp4", ".mov"}
ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac"}
ALLOWED_TEXT_FONTS = {
    "Lobster",
    "Lobster-Bold",
    "Baloo",
    "Baloo-Bold",
    "Fredoka",
    "Fredoka-Bold",
    "Bangers",
    "Bangers-Bold",
    "Luckiest Guy",
    "Luckiest Guy-Bold",
    "Anton",
    "Anton-Bold",
    "Montserrat",
    "Montserrat-Bold",
    "Oswald",
    "Oswald-Bold",
    "Poppins",
    "Poppins-Bold",
    "Inter",
    "Inter-Bold",
    "Nunito",
    "Nunito-Bold",
}
ALLOWED_TEXT_EFFECTS = {"rebote", "fade", "pop", "none"}


def _size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def _add_narrator(video_path: Path, text: str, work_dir: Path, narrator_index: int, music_volume: float) -> None:
    """Generate TTS from text and mix into video, replacing the file in-place."""
    try:
        from gtts import gTTS  # type: ignore
    except ImportError as exc:
        raise RuntimeError("gTTS no esta instalado. Agrega 'gtts' a requirements.txt") from exc

    narrator_audio = work_dir / f"narrator_{narrator_index}.mp3"
    tts = gTTS(text=text, lang="es")
    tts.save(str(narrator_audio))

    output_with_narrator = work_dir / f"narrator_mixed_{narrator_index}.mp4"
    # Mix: reduce music/existing audio and add narrator on top
    filter_complex = (
        f"[0:a]volume={music_volume:.2f}[music];"
        "[1:a]volume=1.0[narr];"
        "[music][narr]amix=inputs=2:duration=first[out]"
    )
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(video_path),
        "-i", str(narrator_audio),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        str(output_with_narrator),
    ]
    result = subprocess.run(cmd, capture_output=True)  # nosec B603
    if result.returncode != 0:
        raise RuntimeError(f"Error mezclando narrador: {result.stderr.decode('utf-8', errors='replace')}")

    # Replace original
    shutil.move(str(output_with_narrator), str(video_path))


async def process_generation(
    clips: list[UploadFile],
    requested_versions: int,
    style_name: str,
    music_file: UploadFile | None,
    music_preset: str | None,
    prompt_context: str,
    text_fonts: list[str],
    text_effects: list[str],
    text_bold: bool,
    drive_folder_id: str,
    centered_text: str,
    drive_file_ids: list[str] | None = None,
    text_mode: str = "two_lines",
    narrator: bool = False,
    oauth_token: str | None = None,
    job_id: str | None = None,
    progress_callback=None,
) -> tuple[str, str, list[GeneratedVideo]]:
    def _progress(step: str, pct: float) -> None:
        if progress_callback:
            progress_callback(step, pct)

    if requested_versions < 1 or requested_versions > settings.max_output_versions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La cantidad de versiones debe estar entre 1 y {settings.max_output_versions}",
        )

    style = pick_style(style_name)

    chosen_fonts = _validate_selection(text_fonts, ALLOWED_TEXT_FONTS, "fuentes")
    chosen_effects = _validate_selection(text_effects, ALLOWED_TEXT_EFFECTS, "efectos")

    job_id, inputs_dir, outputs_dir, work_dir = create_job_dirs(job_id)
    _progress("Guardando archivos...", 0.04)
    visual_styles = _build_visual_style_plan(
        requested_versions=requested_versions,
        chosen_fonts=chosen_fonts,
        chosen_effects=chosen_effects,
        seed=job_id,
    )

    clip_infos: list[MediaInfo] = []
    cleaned_drive_folder = (drive_folder_id or "").strip()

    if clips:
        if len(clips) > settings.max_input_clips:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximo {settings.max_input_clips} clips",
            )

        for idx, upload in enumerate(clips, start=1):
            ext = Path(upload.filename or "").suffix.lower()
            if ext not in ALLOWED_VIDEO_EXTS:
                raise HTTPException(status_code=400, detail=f"Formato no soportado: {upload.filename}")

            filename = f"clip_{idx:02d}{ext}"
            destination = inputs_dir / filename
            await _save_upload(upload, destination)

            if _size_mb(destination) > settings.max_clip_size_mb:
                raise HTTPException(
                    status_code=400,
                    detail=f"{upload.filename} excede {settings.max_clip_size_mb}MB",
                )

            clip_infos.append(probe_media(destination))
    elif drive_file_ids:
        try:
            downloaded = download_drive_files_by_id(drive_file_ids, inputs_dir, access_token=oauth_token)
        except DriveIntegrationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error al descargar archivos de Drive: {exc}") from exc

        for downloaded_file in downloaded:
            if downloaded_file.suffix.lower() not in ALLOWED_VIDEO_EXTS:
                continue
            if _size_mb(downloaded_file) > settings.max_clip_size_mb:
                raise HTTPException(status_code=400, detail=f"{downloaded_file.name} excede {settings.max_clip_size_mb}MB")
            clip_infos.append(probe_media(downloaded_file))
    elif cleaned_drive_folder:
        try:
            downloaded = download_drive_videos(cleaned_drive_folder, inputs_dir, oauth_token=oauth_token)
        except DriveIntegrationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error al descargar videos de Drive: {exc}") from exc

        for downloaded_file in downloaded:
            if downloaded_file.suffix.lower() not in ALLOWED_VIDEO_EXTS:
                continue
            if _size_mb(downloaded_file) > settings.max_clip_size_mb:
                raise HTTPException(status_code=400, detail=f"{downloaded_file.name} excede {settings.max_clip_size_mb}MB")
            clip_infos.append(probe_media(downloaded_file))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir al menos 1 clip o indicar una carpeta de Drive",
        )

    if not clip_infos:
        raise HTTPException(status_code=400, detail="No se encontraron clips validos para procesar")

    selected_music: Path | None = None

    if music_file and music_file.filename:
        ext = Path(music_file.filename).suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTS:
            raise HTTPException(status_code=400, detail="Formato de musica no soportado")
        music_dest = inputs_dir / f"music_upload{ext}"
        await _save_upload(music_file, music_dest)
        if _size_mb(music_dest) > settings.max_music_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"La musica excede {settings.max_music_size_mb}MB",
            )
        selected_music = music_dest
    elif music_preset:
        candidate = music_presets_dir() / music_preset
        if not candidate.exists() or candidate.suffix.lower() not in ALLOWED_AUDIO_EXTS:
            raise HTTPException(status_code=400, detail="Preset de musica invalido")
        selected_music = candidate

    _progress("Analizando clips...", 0.08)
    clip_analyses = analyze_clips(
        clips=clip_infos,
        min_cut=style.min_cut,
        max_cut=style.max_cut,
    )

    results: list[GeneratedVideo] = []

    try:
        for variant_index in range(1, requested_versions + 1):
            pct_start = 0.12 + (variant_index - 1) / requested_versions * 0.83
            _progress(f"Generando variante {variant_index}/{requested_versions}...", pct_start)
            output_name = f"video_{variant_index:02d}.mp4"
            output_path = outputs_dir / output_name
            visual_style = visual_styles[variant_index - 1]

            text_pack = generate_text_pack(
                variant_index=variant_index,
                style=style.name,
                segments=0,
                duration=style.target_duration,
                prompt_context=prompt_context,
                text_mode=text_mode,
            )

            effective_centered = text_pack.centered_text if text_mode == "one_big" else ""

            stats = render_variant(
                clips=clip_infos,
                style=style,
                variant_index=variant_index,
                output_path=output_path,
                work_dir=work_dir,
                music_file=selected_music,
                output_fps=clip_infos[0].fps,
                analyses=clip_analyses,
                overlay_text_1=text_pack.overlay_text_1,
                overlay_text_2=text_pack.overlay_text_2,
                centered_text=effective_centered,
                overlay_font=visual_style["font"],
                overlay_effect=visual_style["effect"],
                overlay_bold=text_bold,
                text_mode=text_mode,
            )

            if narrator:
                if effective_centered:
                    tts_text = effective_centered
                else:
                    parts = [text_pack.overlay_text_1, text_pack.overlay_text_2]
                    tts_text = " ".join(p for p in parts if p and p.strip())
                if tts_text:
                    _add_narrator(
                        video_path=output_path,
                        text=tts_text,
                        work_dir=work_dir,
                        narrator_index=variant_index,
                        music_volume=style.music_volume,
                    )

            results.append(
                GeneratedVideo(
                    variant_index=variant_index,
                    filename=output_name,
                    download_url=f"/api/download/{job_id}/{output_name}",
                    caption=text_pack.caption,
                    overlay_text_1=text_pack.overlay_text_1,
                    overlay_text_2=text_pack.overlay_text_2,
                    centered_text=effective_centered,
                )
            )
            pct_done = 0.12 + variant_index / requested_versions * 0.83
            _progress(f"Variante {variant_index}/{requested_versions} lista", pct_done)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return job_id, style.name, results


def _validate_selection(values: list[str], allowed: set[str], label: str) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"Debes elegir al menos una opcion de {label}")

    invalid = sorted({item for item in cleaned if item not in allowed})
    if invalid:
        raise HTTPException(status_code=400, detail=f"Opciones invalidas en {label}: {', '.join(invalid)}")

    # Keep original order while removing duplicates.
    return list(dict.fromkeys(cleaned))


def _build_visual_style_plan(
    requested_versions: int,
    chosen_fonts: list[str],
    chosen_effects: list[str],
    seed: str,
) -> list[dict[str, str]]:
    combos = [{"font": font, "effect": effect} for font in chosen_fonts for effect in chosen_effects]
    rng = random.Random(seed)

    # Cycle shuffled combo rounds to avoid concentrating output in the same style.
    planned: list[dict[str, str]] = []
    while len(planned) < requested_versions:
        round_combos = combos.copy()
        rng.shuffle(round_combos)
        planned.extend(round_combos)
    return planned[:requested_versions]
