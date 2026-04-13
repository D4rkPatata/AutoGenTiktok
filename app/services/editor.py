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

FONT_CANDIDATE_FILES: dict[str, list[Path]] = {
    "Lobster": [Path("data/fonts/Lobster.ttf"), Path("data/fonts/Lobster-Bold.ttf"), Path("C:/Windows/Fonts/Lobster-Regular.ttf")],
    "Lobster-Bold": [Path("data/fonts/Lobster-Bold.ttf"), Path("data/fonts/Lobster.ttf"), Path("C:/Windows/Fonts/Lobster-Regular.ttf")],
    "Baloo": [Path("data/fonts/Baloo.ttf"), Path("data/fonts/Baloo-Bold.ttf"), Path("C:/Windows/Fonts/Baloo2-Regular.ttf"), Path("C:/Windows/Fonts/Baloo-Regular.ttf")],
    "Baloo-Bold": [Path("data/fonts/Baloo-Bold.ttf"), Path("data/fonts/Baloo.ttf"), Path("C:/Windows/Fonts/Baloo2-Regular.ttf"), Path("C:/Windows/Fonts/Baloo-Regular.ttf")],
    "Fredoka": [Path("data/fonts/Fredoka.ttf"), Path("data/fonts/Fredoka-Bold.ttf"), Path("C:/Windows/Fonts/Fredoka-Regular.ttf")],
    "Fredoka-Bold": [Path("data/fonts/Fredoka-Bold.ttf"), Path("data/fonts/Fredoka.ttf"), Path("C:/Windows/Fonts/Fredoka-Regular.ttf")],
    "Bangers": [Path("data/fonts/Bangers.ttf"), Path("data/fonts/Bangers-Bold.ttf"), Path("C:/Windows/Fonts/Bangers-Regular.ttf")],
    "Bangers-Bold": [Path("data/fonts/Bangers-Bold.ttf"), Path("data/fonts/Bangers.ttf"), Path("C:/Windows/Fonts/Bangers-Regular.ttf")],
    "Luckiest Guy": [Path("data/fonts/LuckiestGuy.ttf"), Path("data/fonts/LuckiestGuy-Bold.ttf"), Path("C:/Windows/Fonts/LuckiestGuy-Regular.ttf")],
    "Luckiest Guy-Bold": [Path("data/fonts/LuckiestGuy-Bold.ttf"), Path("data/fonts/LuckiestGuy.ttf"), Path("C:/Windows/Fonts/LuckiestGuy-Regular.ttf")],
    "Anton": [Path("data/fonts/Anton.ttf"), Path("data/fonts/Anton-Bold.ttf"), Path("C:/Windows/Fonts/Anton-Regular.ttf")],
    "Anton-Bold": [Path("data/fonts/Anton-Bold.ttf"), Path("data/fonts/Anton.ttf"), Path("C:/Windows/Fonts/Anton-Regular.ttf")],
    "Montserrat": [Path("data/fonts/Montserrat.ttf"), Path("data/fonts/Montserrat-Bold.ttf"), Path("C:/Windows/Fonts/Montserrat-Regular.ttf")],
    "Montserrat-Bold": [Path("data/fonts/Montserrat-Bold.ttf"), Path("data/fonts/Montserrat.ttf"), Path("C:/Windows/Fonts/Montserrat-Regular.ttf")],
    "Oswald": [Path("data/fonts/Oswald.ttf"), Path("data/fonts/Oswald-Bold.ttf"), Path("C:/Windows/Fonts/Oswald-Regular.ttf")],
    "Oswald-Bold": [Path("data/fonts/Oswald-Bold.ttf"), Path("data/fonts/Oswald.ttf"), Path("C:/Windows/Fonts/Oswald-Regular.ttf")],
    "Poppins": [Path("data/fonts/Poppins.ttf"), Path("data/fonts/Poppins-Bold.ttf"), Path("C:/Windows/Fonts/Poppins-Regular.ttf")],
    "Poppins-Bold": [Path("data/fonts/Poppins-Bold.ttf"), Path("data/fonts/Poppins.ttf"), Path("C:/Windows/Fonts/Poppins-Regular.ttf")],
    "Inter": [Path("data/fonts/Inter.ttf"), Path("data/fonts/Inter-Bold.ttf"), Path("C:/Windows/Fonts/Inter-Regular.ttf")],
    "Inter-Bold": [Path("data/fonts/Inter-Bold.ttf"), Path("data/fonts/Inter.ttf"), Path("C:/Windows/Fonts/Inter-Regular.ttf")],
    "Nunito": [Path("data/fonts/Nunito.ttf"), Path("data/fonts/Nunito-Bold.ttf"), Path("C:/Windows/Fonts/Nunito-Regular.ttf")],
    "Nunito-Bold": [Path("data/fonts/Nunito-Bold.ttf"), Path("data/fonts/Nunito.ttf"), Path("C:/Windows/Fonts/Nunito-Regular.ttf")],
}

FALLBACK_FONT_FILES = [
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
]


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


def _mix_music(
    base_video: Path,
    music_file: Path,
    profile: StyleProfile,
    duration: float,
    ending_starts_at: float,
    out_path: Path,
) -> None:
    fade_out_start = max(duration - 1.2, 0.0)
    ending_music_gain = 0.8

    filter_complex = (
        f"[0:a]atrim=0:{duration:.3f},asetpts=N/SR/TB,volume={profile.music_volume:.2f},"
        f"volume='if(lt(t,{ending_starts_at:.3f}),1,{ending_music_gain:.2f})',"
        f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.3f}:d=1.2,alimiter=limit=0.96[a]"
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


def _resolve_font_path(font_name: str) -> Path | None:
    for candidate in FONT_CANDIDATE_FILES.get(font_name, []):
        if candidate.exists():
            return candidate
    for fallback in FALLBACK_FONT_FILES:
        if fallback.exists():
            return fallback
    return None


def _build_drawtext(
    text: str,
    start: float,
    end: float,
    font_size: int,
    y_expr: str,
    box_color: str,
    box_border: int,
    font_name: str,
    is_bold: bool,
    use_box: bool = True,
    alpha_expr: str | None = None,
) -> str:
    # Force uppercase for all overlays.
    safe_text = _escape_drawtext((text or "").upper())
    safe_font_name = _escape_drawtext(font_name)
    font_path = _resolve_font_path(font_name)

    font_opt = f"font='{safe_font_name}'"
    if font_path is not None:
        font_opt = f"fontfile='{_escape_drawtext(font_path.as_posix())}'"

    enable_expr = f"between(t,{start:.2f},{end:.2f})"
    box_flag = 0
    border_width = "2.2" if is_bold else "0.0"
    alpha_clause = ""
    if alpha_expr:
        alpha_clause = f"alpha='{alpha_expr}':"

    return (
        "drawtext="
        f"{font_opt}:text='{safe_text}':"
        f"fontsize={font_size}:"
        "fontcolor=white:line_spacing=8:"
        "x=(w-text_w)/2:"
        f"y={y_expr}:"
        f"borderw={border_width}:bordercolor=black@0.90:"
        f"{alpha_clause}"
        f"box={box_flag}:boxcolor={box_color}:boxborderw={box_border}:"
        f"enable='{enable_expr}'"
    )


def _build_effect_layers(
    text: str,
    start: float,
    end: float,
    font_size: int,
    y_base: str,
    box_color: str,
    box_border: int,
    font_name: str,
    effect: str,
    overlay_bold: bool,
) -> list[str]:
    intro_end = min(start + 0.55, end)
    layers: list[str] = []

    if effect == "fade":
        fade_alpha = f"if(lt(t,{start:.3f}),0,if(lt(t,{intro_end:.3f}),(t-{start:.3f})/{max(intro_end-start,0.01):.3f},1))"
        layers.append(
            _build_drawtext(
                text=text,
                start=start,
                end=end,
                font_size=font_size,
                y_expr=y_base,
                box_color=box_color,
                box_border=box_border,
                font_name=font_name,
                is_bold=overlay_bold,
                use_box=True,
                alpha_expr=fade_alpha,
            )
        )
        return layers

    if effect == "pop":
        pop_in_end = min(start + 0.16, end)
        settle_end = min(start + 0.36, end)
        layers.append(
            _build_drawtext(
                text=text,
                start=start,
                end=pop_in_end,
                font_size=int(font_size * 1.34),
                y_expr=y_base,
                box_color=box_color,
                box_border=box_border,
                font_name=font_name,
                is_bold=overlay_bold,
                use_box=False,
            )
        )
        layers.append(
            _build_drawtext(
                text=text,
                start=pop_in_end,
                end=settle_end,
                font_size=font_size,
                y_expr=y_base,
                box_color=box_color,
                box_border=box_border,
                font_name=font_name,
                is_bold=overlay_bold,
                use_box=True,
            )
        )
        if settle_end < end:
            layers.append(
                _build_drawtext(
                    text=text,
                    start=settle_end,
                    end=end,
                    font_size=font_size,
                    y_expr=y_base,
                    box_color=box_color,
                    box_border=box_border,
                    font_name=font_name,
                    is_bold=overlay_bold,
                    use_box=True,
                )
            )
        return layers

    # rebote
    b1 = min(start + 0.12, end)
    b2 = min(start + 0.24, end)
    b3 = min(start + 0.38, end)
    layers.extend(
        [
            _build_drawtext(text, start, b1, font_size, f"({y_base})-170", box_color, box_border, font_name, overlay_bold, False),
            _build_drawtext(text, b1, b2, font_size, f"({y_base})+55", box_color, box_border, font_name, overlay_bold, False),
            _build_drawtext(text, b2, b3, font_size, f"({y_base})-20", box_color, box_border, font_name, overlay_bold, True),
        ]
    )
    if b3 < end:
        layers.append(_build_drawtext(text, b3, end, font_size, y_base, box_color, box_border, font_name, overlay_bold, True))
    return layers


def _apply_text_overlays(
    in_path: Path,
    out_path: Path,
    duration: float,
    output_fps: float,
    overlay_text_1: str,
    overlay_text_2: str,
    overlay_font: str,
    overlay_effect: str,
    overlay_bold: bool,
) -> None:
    text_1 = (overlay_text_1 or "").strip()
    text_2 = (overlay_text_2 or "").strip()

    if not text_1 and not text_2:
        shutil.copy(in_path, out_path)
        return

    d = max(duration, 1.0)
    first_start = min(1.0, max(0.0, d - 0.2))
    first_end = min(7.0, max(first_start + 0.4, d - 1.2))

    second_start = min(8.0, max(first_end + 0.2, d - 1.1))
    second_end = max(second_start + 0.25, d - 1.0)

    draw_1_layers = _build_effect_layers(
        text=text_1,
        start=first_start,
        end=first_end,
        font_size=75,
        y_base="h*0.14",
        box_color="black@0.42",
        box_border=18,
        font_name=overlay_font,
        effect=overlay_effect,
        overlay_bold=overlay_bold,
    )
    draw_2_layers = _build_effect_layers(
        text=text_2,
        start=second_start,
        end=second_end,
        font_size=71,
        y_base="h*0.79",
        box_color="black@0.36",
        box_border=16,
        font_name=overlay_font,
        effect=overlay_effect,
        overlay_bold=overlay_bold,
    )

    filter_chain = ",".join(draw_1_layers + draw_2_layers)

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
    overlay_font: str = "Inter",
    overlay_effect: str = "fade",
    overlay_bold: bool = True,
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

    overlayed = work_dir / f"v{variant_index}_overlayed.mp4"
    _apply_text_overlays(
        in_path=base_path,
        out_path=overlayed,
        duration=final_duration,
        output_fps=output_fps,
        overlay_text_1=overlay_text_1,
        overlay_text_2=overlay_text_2,
        overlay_font=overlay_font,
        overlay_effect=overlay_effect,
        overlay_bold=overlay_bold,
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
    concatenated = work_dir / f"v{variant_index}_with_ending.mp4"
    _concat_with_ending(
        main_faded=faded_main,
        ending_path=ending_path,
        output_fps=output_fps,
        out_path=concatenated,
    )

    total_duration = final_duration + ending_duration
    if music_file is None:
        shutil.copy(concatenated, output_path)
    else:
        _mix_music(
            base_video=concatenated,
            music_file=music_file,
            profile=style,
            duration=total_duration,
            ending_starts_at=final_duration,
            out_path=output_path,
        )

    return {
        "segments": len(segments),
        "duration": round(total_duration, 2),
    }
