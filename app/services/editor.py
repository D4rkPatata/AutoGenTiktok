from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.analyzer import ClipAnalysis
from app.services.probe import MediaInfo, probe_media
from app.utils.ffmpeg import run_cmd


@dataclass
class StyleProfile:
    name: str
    min_cut: float
    max_cut: float
    transition: float
    target_duration: float
    music_volume: float


STYLE_PROFILES: dict[str, StyleProfile] = {
    "clean_fast": StyleProfile(
        name="clean_fast",
        min_cut=1.0,
        max_cut=2.8,
        transition=0.20,
        target_duration=20.0,
        music_volume=0.35,
    ),
    "aggressive": StyleProfile(
        name="aggressive",
        min_cut=0.8,
        max_cut=2.0,
        transition=0.16,
        target_duration=16.0,
        music_volume=0.32,
    ),
    "smooth": StyleProfile(
        name="smooth",
        min_cut=1.4,
        max_cut=3.5,
        transition=0.24,
        target_duration=24.0,
        music_volume=0.40,
    ),
}


@dataclass
class Segment:
    source: Path
    start: float
    duration: float
    has_audio: bool


def pick_style(style: str | None) -> StyleProfile:
    if style and style in STYLE_PROFILES:
        return STYLE_PROFILES[style]
    return STYLE_PROFILES["clean_fast"]


def _random_start(duration: float, cut: float, rng: random.Random) -> float:
    safe_start = max(0.0, duration * 0.05)
    safe_end = max(safe_start, duration - cut - (duration * 0.05))
    if safe_end <= safe_start:
        return 0.0
    return rng.uniform(safe_start, safe_end)


def build_variant_segments(
    clips: list[MediaInfo],
    style: StyleProfile,
    seed: int,
    analyses: dict[Path, ClipAnalysis] | None = None,
) -> list[Segment]:
    rng = random.Random(seed)
    target = style.target_duration
    segments: list[Segment] = []
    media_by_path = {clip.path: clip for clip in clips}

    used_ranges: dict[Path, list[tuple[float, float]]] = {clip.path: [] for clip in clips}

    def overlaps_used(path: Path, start: float, duration: float, threshold: float = 0.72) -> bool:
        end = start + duration
        for used_start, used_end in used_ranges[path]:
            inter = max(0.0, min(end, used_end) - max(start, used_start))
            if inter <= 0:
                continue
            overlap_ratio = inter / min(duration, used_end - used_start)
            if overlap_ratio > threshold:
                return True
        return False

    def to_segment(path: Path, start: float, duration: float) -> Segment:
        media = media_by_path[path]
        return Segment(source=path, start=start, duration=duration, has_audio=media.has_audio)

    def random_fallback_segment(path: Path, remaining: float) -> Segment | None:
        media = media_by_path[path]
        max_cut = min(style.max_cut, media.duration, remaining)
        min_cut = min(style.min_cut, max_cut)
        if max_cut < 0.65:
            return None
        cut_duration = rng.uniform(min_cut, max_cut)
        if cut_duration < 0.65:
            return None
        start = _random_start(media.duration, cut_duration, rng)
        if overlaps_used(path, start, cut_duration):
            return None
        return to_segment(path, start, cut_duration)

    # Hook: force a strong opening beat between 1 and 2 seconds.
    opener: Segment | None = None
    ranked_openers: list[tuple[float, Segment]] = []
    if analyses:
        for clip in clips:
            analysis = analyses.get(clip.path)
            if not analysis:
                continue
            for candidate in analysis.candidates:
                if 1.0 <= candidate.duration <= 2.2:
                    ranked_openers.append(
                        (
                            candidate.score + rng.uniform(0.0, 0.2),
                            to_segment(clip.path, candidate.start, candidate.duration),
                        )
                    )

    if ranked_openers:
        ranked_openers.sort(key=lambda item: item[0], reverse=True)
        opener = ranked_openers[0][1]
    else:
        opener_clip = rng.choice(clips)
        opener_duration = min(max(1.2, style.min_cut), min(2.0, opener_clip.duration))
        opener_start = _random_start(opener_clip.duration, opener_duration, rng)
        opener = Segment(
            source=opener_clip.path,
            start=opener_start,
            duration=opener_duration,
            has_audio=opener_clip.has_audio,
        )

    segments.append(opener)
    used_ranges[opener.source].append((opener.start, opener.start + opener.duration))
    elapsed = opener.duration

    max_iterations = 220
    attempts = 0

    while elapsed < target and len(segments) < 16 and attempts < max_iterations:
        attempts += 1
        remaining = target - elapsed
        if remaining < 0.7:
            break

        # Avoid repeating same source clip when possible.
        last_source = segments[-1].source
        clip_candidates = [clip for clip in clips if clip.path != last_source] or clips

        ranked_choices: list[tuple[float, Segment]] = []
        if analyses:
            for clip in clip_candidates:
                analysis = analyses.get(clip.path)
                if not analysis:
                    continue
                for candidate in analysis.candidates:
                    if candidate.duration > remaining + 0.35:
                        continue
                    if candidate.duration < 0.65:
                        continue
                    if overlaps_used(clip.path, candidate.start, candidate.duration):
                        continue
                    score = candidate.score + rng.uniform(0.0, 0.18)
                    ranked_choices.append(
                        (score, to_segment(clip.path, candidate.start, candidate.duration))
                    )

        picked: Segment | None = None
        if ranked_choices:
            ranked_choices.sort(key=lambda item: item[0], reverse=True)
            top_pool = ranked_choices[: min(6, len(ranked_choices))]
            picked = rng.choice(top_pool)[1]
        else:
            for candidate_clip in rng.sample(clip_candidates, k=len(clip_candidates)):
                fallback = random_fallback_segment(candidate_clip.path, remaining)
                if fallback is not None:
                    picked = fallback
                    break

        if picked is None:
            break

        segments.append(picked)
        used_ranges[picked.source].append((picked.start, picked.start + picked.duration))
        elapsed += picked.duration - style.transition

    return segments


def _extract_segment(segment: Segment, output_path: Path, output_fps: float) -> None:
    video_filter = (
        f"scale={settings.target_width}:{settings.target_height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={settings.target_width}:{settings.target_height},"
        f"fps={output_fps:.6f},setsar=1"
    )

    if segment.has_audio:
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{segment.start:.3f}",
            "-t",
            f"{segment.duration:.3f}",
            "-i",
            str(segment.source),
            "-vf",
            video_filter,
            "-af",
            "aresample=async=1:first_pts=0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    else:
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{segment.start:.3f}",
            "-t",
            f"{segment.duration:.3f}",
            "-i",
            str(segment.source),
            "-f",
            "lavfi",
            "-t",
            f"{segment.duration:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            video_filter,
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    run_cmd(cmd)


def _compose_with_transitions(segment_paths: list[Path], durations: list[float], transition: float, out_path: Path) -> float:
    if len(segment_paths) == 1:
        shutil.copy(segment_paths[0], out_path)
        return durations[0]

    cmd = [settings.ffmpeg_bin, "-y"]
    for path in segment_paths:
        cmd.extend(["-i", str(path)])

    filters: list[str] = []

    for i in range(1, len(segment_paths)):
        prev_v = "0:v" if i == 1 else f"v{i-1}"
        offset = sum(durations[:i]) - (transition * i)
        filters.append(
            f"[{prev_v}][{i}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}[v{i}]"
        )

    for i in range(1, len(segment_paths)):
        prev_a = "0:a" if i == 1 else f"a{i-1}"
        filters.append(f"[{prev_a}][{i}:a]acrossfade=d={transition:.3f}[a{i}]")

    filter_complex = ";".join(filters)
    last_idx = len(segment_paths) - 1

    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            f"[v{last_idx}]",
            "-map",
            f"[a{last_idx}]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    )
    run_cmd(cmd)

    total_duration = sum(durations) - (transition * (len(durations) - 1))
    return max(total_duration, 1.0)


def _mix_music(base_video: Path, music_file: Path, profile: StyleProfile, duration: float, out_path: Path) -> None:
    fade_out_start = max(duration - 1.2, 0.0)

    filter_complex = (
        f"[0:a]atrim=0:{duration:.3f},asetpts=N/SR/TB,volume={profile.music_volume:.2f},"
        f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.3f}:d=1.2[m];"
        "[1:a]volume=1.0[o];"
        "[m][o]sidechaincompress=threshold=0.06:ratio=8:attack=20:release=250[duck];"
        "[o][duck]amix=inputs=2:weights='1 0.9':normalize=0,alimiter=limit=0.96[a]"
    )

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(music_file),
        "-i",
        str(base_video),
        "-filter_complex",
        filter_complex,
        "-map",
        "1:v",
        "-map",
        "[a]",
        "-shortest",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    run_cmd(cmd)


def _escape_drawtext(text: str) -> str:
    escaped = (text or "").strip()
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(",", "\\,")
    escaped = escaped.replace("[", "\\[")
    escaped = escaped.replace("]", "\\]")
    escaped = escaped.replace("%", "\\%")
    return escaped


def _apply_text_overlays(
    in_path: Path,
    out_path: Path,
    duration: float,
    output_fps: float,
    overlay_text_1: str,
    overlay_text_2: str,
) -> None:
    text_1 = _escape_drawtext(overlay_text_1)
    text_2 = _escape_drawtext(overlay_text_2)

    if not text_1 and not text_2:
        shutil.copy(in_path, out_path)
        return

    d = max(duration, 1.0)
    first_start = min(max(0.35, d * 0.08), max(0.35, d - 0.9))
    first_end = min(d * 0.34, first_start + 3.2)
    second_end = max(d - 0.35, d * 0.98)
    second_start = max(second_end - 3.0, d * 0.62)

    first_enable = f"between(t,{first_start:.2f},{first_end:.2f})"
    second_enable = f"between(t,{second_start:.2f},{second_end:.2f})"

    draw_1 = (
        "drawtext="
        f"font='Arial':text='{text_1}':"
        "fontsize=60:fontcolor=white:line_spacing=8:"
        "x=(w-text_w)/2:y=h*0.14:"
        "box=1:boxcolor=black@0.42:boxborderw=18:"
        f"enable='{first_enable}'"
    )
    draw_2 = (
        "drawtext="
        f"font='Arial':text='{text_2}':"
        "fontsize=56:fontcolor=white:line_spacing=8:"
        "x=(w-text_w)/2:y=h*0.79:"
        "box=1:boxcolor=black@0.36:boxborderw=16:"
        f"enable='{second_enable}'"
    )

    filter_chain = f"{draw_1},{draw_2}"

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(in_path),
        "-vf",
        filter_chain,
        "-c:v",
        "libx264",
        "-r",
        f"{output_fps:.6f}",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    run_cmd(cmd)


def _apply_tail_fade(main_video: Path, out_path: Path, duration: float, output_fps: float) -> None:
    fade_duration = 1.0
    fade_start = max(duration - fade_duration, 0.0)
    filter_complex = (
        f"[0:v]fade=t=out:st={fade_start:.3f}:d={fade_duration:.3f}[v];"
        f"[0:a]afade=t=out:st={fade_start:.3f}:d={fade_duration:.3f}[a]"
    )

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(main_video),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-r",
        f"{output_fps:.6f}",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    run_cmd(cmd)


def _validate_ending_clip(ending_path: Path, output_fps: float) -> float:
    if not ending_path.exists():
        raise RuntimeError(f"No se encontro ending en: {ending_path}")

    ending_info = probe_media(ending_path)
    if ending_info.width != settings.target_width or ending_info.height != settings.target_height:
        raise RuntimeError(
            "El ending debe estar en 1080x1920 para no modificarlo internamente en el pipeline"
        )
    if not ending_info.has_audio:
        raise RuntimeError("El ending debe incluir audio para concatenacion fluida")

    fps_diff = abs(ending_info.fps - output_fps)
    if fps_diff > 0.05:
        raise RuntimeError(
            f"FPS del ending ({ending_info.fps:.3f}) no coincide con FPS original ({output_fps:.3f})"
        )

    return max(ending_info.duration, 0.01)


def _concat_with_ending(main_faded: Path, ending_path: Path, output_fps: float, out_path: Path) -> None:
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(main_faded),
        "-i",
        str(ending_path),
        "-filter_complex",
        "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-r",
        f"{output_fps:.6f}",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    run_cmd(cmd)


def render_variant(
    clips: list[MediaInfo],
    style: StyleProfile,
    variant_index: int,
    output_path: Path,
    work_dir: Path,
    music_file: Path | None,
    output_fps: float,
    analyses: dict[Path, ClipAnalysis] | None = None,
    overlay_text_1: str = "",
    overlay_text_2: str = "",
) -> dict:
    segments = build_variant_segments(clips, style, seed=variant_index * 7919, analyses=analyses)
    if not segments:
        raise RuntimeError("Could not build segments for this variant")

    segment_paths: list[Path] = []
    durations: list[float] = []
    for idx, segment in enumerate(segments, start=1):
        path = work_dir / f"v{variant_index}_seg_{idx:02d}.mp4"
        _extract_segment(segment, path, output_fps=output_fps)
        segment_paths.append(path)
        durations.append(segment.duration)

    base_path = work_dir / f"v{variant_index}_base.mp4"
    final_duration = _compose_with_transitions(segment_paths, durations, style.transition, base_path)

    if music_file is None:
        shutil.copy(base_path, output_path)
    else:
        _mix_music(base_path, music_file, style, final_duration, output_path)

    overlayed = work_dir / f"v{variant_index}_overlayed.mp4"
    _apply_text_overlays(
        in_path=output_path,
        out_path=overlayed,
        duration=final_duration,
        output_fps=output_fps,
        overlay_text_1=overlay_text_1,
        overlay_text_2=overlay_text_2,
    )

    faded_main = work_dir / f"v{variant_index}_faded_main.mp4"
    _apply_tail_fade(
        main_video=overlayed,
        out_path=faded_main,
        duration=final_duration,
        output_fps=output_fps,
    )

    ending_path = settings.ending_clip_path
    ending_duration = _validate_ending_clip(ending_path=ending_path, output_fps=output_fps)
    _concat_with_ending(
        main_faded=faded_main,
        ending_path=ending_path,
        output_fps=output_fps,
        out_path=output_path,
    )

    return {
        "segments": len(segments),
        "duration": round(final_duration + ending_duration, 2),
    }
