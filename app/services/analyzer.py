from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.probe import MediaInfo
from app.utils.ffmpeg import run_cmd


@dataclass
class CandidateWindow:
    start: float
    duration: float
    score: float


@dataclass
class ClipAnalysis:
    media: MediaInfo
    scene_times: list[float]
    candidates: list[CandidateWindow]


_SCENE_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


def _detect_scene_times(video_path: Path, threshold: float = 0.20) -> list[float]:
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(video_path),
        "-an",
        "-filter:v",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]

    try:
        result = run_cmd(cmd)
    except Exception:
        return []

    times = [float(match.group(1)) for match in _SCENE_RE.finditer(result.stderr)]
    # Keep unique ordered times with small rounding to prevent duplicates.
    seen: set[float] = set()
    unique_times: list[float] = []
    for t in sorted(times):
        key = round(t, 2)
        if key in seen:
            continue
        seen.add(key)
        unique_times.append(t)
    return unique_times


def _clamp_start(duration: float, start: float, cut_duration: float) -> float:
    max_start = max(duration - cut_duration, 0.0)
    return max(0.0, min(start, max_start))


def _build_candidates(media: MediaInfo, scene_times: list[float], min_cut: float, max_cut: float) -> list[CandidateWindow]:
    duration = media.duration
    if duration < 0.65:
        return []

    local_max_cut = min(max_cut, duration)
    local_min_cut = min(min_cut, local_max_cut)

    if local_max_cut < 0.65:
        return []

    mid_cut = (local_min_cut + local_max_cut) / 2
    cut_templates = sorted({round(local_min_cut, 2), round(mid_cut, 2), round(local_max_cut, 2)})

    anchors = list(scene_times)
    if not anchors:
        step = max(duration / 4, 1.0)
        anchors = [min(step * i, duration * 0.95) for i in range(1, 4)]

    candidates: list[CandidateWindow] = []

    for anchor in anchors:
        near_scenes = sum(1 for t in scene_times if abs(t - anchor) <= 1.1)
        for cut in cut_templates:
            if cut > duration:
                continue
            start = _clamp_start(duration, anchor - (cut * 0.38), cut)
            center = start + cut / 2
            center_ratio = abs((center / duration) - 0.5)
            center_bonus = max(0.0, 0.22 - center_ratio)
            score = 1.1 + (near_scenes * 0.28) + center_bonus
            candidates.append(CandidateWindow(start=start, duration=cut, score=score))

    # Add neutral fallback windows so clips without many scene changes still participate.
    neutral_slots = 5
    step = max((duration - local_min_cut) / neutral_slots, 0.5)
    for i in range(neutral_slots):
        cut = local_min_cut if i % 2 == 0 else min(mid_cut, duration)
        start = _clamp_start(duration, i * step, cut)
        candidates.append(CandidateWindow(start=start, duration=cut, score=0.65))

    dedup: dict[tuple[float, float], CandidateWindow] = {}
    for c in candidates:
        key = (round(c.start, 2), round(c.duration, 2))
        existing = dedup.get(key)
        if existing is None or c.score > existing.score:
            dedup[key] = c

    ranked = sorted(dedup.values(), key=lambda c: c.score, reverse=True)
    return ranked[:80]


def analyze_clips(clips: list[MediaInfo], min_cut: float, max_cut: float) -> dict[Path, ClipAnalysis]:
    analyses: dict[Path, ClipAnalysis] = {}

    for media in clips:
        scene_times = _detect_scene_times(media.path)
        candidates = _build_candidates(media, scene_times, min_cut=min_cut, max_cut=max_cut)
        analyses[media.path] = ClipAnalysis(media=media, scene_times=scene_times, candidates=candidates)

    return analyses
