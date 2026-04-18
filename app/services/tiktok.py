from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
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


def send_drafts(
    video_paths: list[Path],
    access_token: str | None = None,
    open_id: str | None = None,
    public_urls: list[str] | None = None,
    captions: list[str] | None = None,
) -> list[TiktokDraftResult]:
    effective_token = access_token or settings.tiktok_access_token

    connected, message = get_connection_status(session_token=access_token, session_open_id=open_id)
    if not connected:
        raise TiktokIntegrationError(message)

    endpoint = (settings.tiktok_draft_endpoint or "").strip()
    if not endpoint:
        raise TiktokIntegrationError("Falta TIKTOK_DRAFT_ENDPOINT")

    use_pull = bool(public_urls and len(public_urls) == len(video_paths))

    results: list[TiktokDraftResult] = []

    for idx, video_path in enumerate(video_paths):
        caption = (captions[idx] if captions and idx < len(captions) else video_path.stem)[:150]
        file_size = video_path.stat().st_size
        if use_pull:
            source_info: dict = {
                "source": "PULL_FROM_URL",
                "video_url": public_urls[idx],  # type: ignore[index]
            }
        else:
            source_info = {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            }

        payload = {
            "post_info": {
                "title": caption,
                "privacy_level": "SELF_ONLY",
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": source_info,
        }

        headers = {
            "Authorization": f"Bearer {effective_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
        }

        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            try:
                with urlopen(req, timeout=30) as response:  # nosec B310
                    raw = response.read().decode("utf-8", errors="ignore")
            except HTTPError as http_exc:
                body = http_exc.read().decode("utf-8", errors="ignore")
                results.append(TiktokDraftResult(filename=video_path.name, ok=False, message=f"HTTP {http_exc.code}: {body[:400]}"))
                continue

            init_data = json.loads(raw)
            err = init_data.get("error", {})
            if err.get("code", "ok") != "ok":
                results.append(TiktokDraftResult(filename=video_path.name, ok=False, message=err.get("message", raw[:240])))
                continue

            upload_url = init_data.get("data", {}).get("upload_url", "")
            if not upload_url:
                results.append(TiktokDraftResult(filename=video_path.name, ok=False, message=f"TikTok no devolvió upload_url. Respuesta: {raw[:240]}"))
                continue

            # Step 2: upload the video bytes
            video_bytes = video_path.read_bytes()
            file_size = len(video_bytes)
            upload_req = Request(  # nosec B310
                upload_url,
                data=video_bytes,
                method="PUT",
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                },
            )
            with urlopen(upload_req, timeout=300) as upload_resp:  # nosec B310
                _ = upload_resp.read()

            results.append(TiktokDraftResult(filename=video_path.name, ok=True, message="Enviado a TikTok drafts"))
        except Exception as exc:  # pragma: no cover
            results.append(TiktokDraftResult(filename=video_path.name, ok=False, message=str(exc)))

    return results
