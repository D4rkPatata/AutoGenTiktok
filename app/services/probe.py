from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from app.utils.ffmpeg import ffprobe_json


@dataclass
class MediaInfo:
    path: Path
    duration: float
    has_audio: bool
    width: int
    height: int
    fps: float


def _parse_fps(rate: str | None) -> float:
    if not rate:
        return 30.0

    try:
        fps = float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        return 30.0

    if fps <= 0:
        return 30.0
    return fps


def probe_media(file_path: Path) -> MediaInfo:
    raw = ffprobe_json(file_path)
    streams = raw.get("streams", [])
    fmt = raw.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise ValueError(f"No video stream found in {file_path.name}")

    duration = float(fmt.get("duration") or video_stream.get("duration") or 0)
    if duration <= 0:
        duration = 1.0

    fps = _parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))

    return MediaInfo(
        path=file_path,
        duration=duration,
        has_audio=audio_stream is not None,
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        fps=fps,
    )
