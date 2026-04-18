from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from app.config import settings
from app.schemas import TiktokDraftResult


class TiktokIntegrationError(RuntimeError):
    pass


def get_connection_status(session_token: str | None = None, session_open_id: str | None = None) -> tuple[bool, str]:
    if session_token:
        return True, "TikTok conectado via OAuth"
    if settings.tiktok_access_token and settings.tiktok_open_id:
        return True, "TikTok listo (token manual)"
    return False, "Conecta tu cuenta TikTok para enviar drafts"


def send_drafts(video_paths: list[Path], access_token: str | None = None, open_id: str | None = None) -> list[TiktokDraftResult]:
    effective_token = access_token or settings.tiktok_access_token
    effective_open_id = open_id or settings.tiktok_open_id

    connected, message = get_connection_status(session_token=access_token, session_open_id=open_id)
    if not connected:
        raise TiktokIntegrationError(message)

    endpoint = (settings.tiktok_draft_endpoint or "").strip()
    if not endpoint:
        raise TiktokIntegrationError("Falta TIKTOK_DRAFT_ENDPOINT")

    results: list[TiktokDraftResult] = []

    for video_path in video_paths:
        payload = {
            "post_info": {
                "title": video_path.stem,
                "privacy_level": "SELF_ONLY",
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_path.stat().st_size,
                "chunk_size": video_path.stat().st_size,
                "total_chunk_count": 1,
                "file_name": video_path.name,
            },
        }

        headers = {
            "Authorization": f"Bearer {effective_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if effective_open_id:
            headers["X-Tt-Openid"] = effective_open_id

        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(req, timeout=30) as response:  # nosec B310
                raw = response.read().decode("utf-8", errors="ignore")
            results.append(TiktokDraftResult(filename=video_path.name, ok=True, message=raw[:240]))
        except Exception as exc:  # pragma: no cover
            results.append(TiktokDraftResult(filename=video_path.name, ok=False, message=str(exc)))

    return results
