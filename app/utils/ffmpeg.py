import json
import subprocess
from pathlib import Path

from app.config import settings


class FFmpegError(RuntimeError):
    pass


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise FFmpegError(f"Command failed: {' '.join(cmd)}\n{process.stderr}")
    return process


def ffprobe_json(file_path: Path) -> dict:
    cmd = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(file_path),
    ]
    result = run_cmd(cmd)
    return json.loads(result.stdout)
