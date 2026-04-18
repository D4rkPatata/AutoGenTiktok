from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from app.config import settings


class DriveIntegrationError(RuntimeError):
    pass


_FOLDER_ID_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")


def _extract_folder_id(folder_or_link: str) -> str:
    raw = (folder_or_link or "").strip()
    if not raw:
        return ""

    # Support plain folder IDs directly.
    if "http://" not in raw and "https://" not in raw:
        return raw

    parsed = urlparse(raw)
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        return query["id"][0].strip()

    match = _FOLDER_ID_RE.search(parsed.path or "")
    if match:
        return match.group(1).strip()

    return ""


def _read_json(url: str, access_token: str | None = None) -> dict:
    headers: dict[str, str] = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as response:  # nosec B310
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def list_folder_contents_oauth(parent_id: str, access_token: str) -> dict:
    """Returns {'folders': [...], 'files': [...]} for the given parent using OAuth."""
    base = (
        "https://www.googleapis.com/drive/v3/files"
        "?supportsAllDrives=true&includeItemsFromAllDrives=true&orderBy=name"
    )

    folder_query = quote(
        f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    folder_fields = quote("files(id,name)")
    folders_payload = _read_json(f"{base}&q={folder_query}&fields={folder_fields}", access_token=access_token)

    file_query = quote(f"'{parent_id}' in parents and mimeType contains 'video/' and trashed=false")
    file_fields = quote("files(id,name,mimeType,size)")
    files_payload = _read_json(f"{base}&q={file_query}&fields={file_fields}", access_token=access_token)

    return {
        "folders": folders_payload.get("files") or [],
        "files": files_payload.get("files") or [],
    }


def download_drive_files_by_id(
    file_ids: list[str],
    destination_dir: Path,
    access_token: str | None = None,
) -> list[Path]:
    """Download specific Drive files by their IDs."""
    api_key = (settings.google_api_key or "").strip()
    destination_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    for file_id in file_ids[: settings.max_drive_input_clips]:
        # Get file metadata to retrieve the filename
        meta_url = (
            f"https://www.googleapis.com/drive/v3/files/{quote(file_id)}"
            "?fields=name,mimeType&supportsAllDrives=true"
        )
        if access_token:
            meta = _read_json(meta_url, access_token=access_token)
            media_url = f"https://www.googleapis.com/drive/v3/files/{quote(file_id)}?alt=media&supportsAllDrives=true"
            req = Request(media_url, headers={"Authorization": f"Bearer {access_token}"})
        elif api_key:
            meta = _read_json(f"{meta_url}&key={quote(api_key)}")
            media_url = f"https://www.googleapis.com/drive/v3/files/{quote(file_id)}?alt=media&supportsAllDrives=true&key={quote(api_key)}"
            req = Request(media_url)
        else:
            raise DriveIntegrationError("Falta autenticacion para descargar archivos de Drive")

        filename = str(meta.get("name") or f"video_{file_id}.mp4")
        safe_name = Path(filename).name
        out_path = destination_dir / safe_name

        with urlopen(req, timeout=120) as response:  # nosec B310
            with out_path.open("wb") as output_file:
                shutil.copyfileobj(response, output_file)

        downloaded.append(out_path)

    if not downloaded:
        raise DriveIntegrationError("No se pudo descargar ningun archivo de Drive")
    return downloaded


def list_subfolders_oauth(parent_id: str, access_token: str) -> list[dict]:
    """List subfolders inside parent_id using an OAuth access token."""
    query = quote(f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false")
    fields = quote("files(id,name)")
    url = (
        "https://www.googleapis.com/drive/v3/files"
        f"?q={query}&fields={fields}&supportsAllDrives=true&includeItemsFromAllDrives=true"
    )
    payload = _read_json(url, access_token=access_token)
    return payload.get("files") or []


def list_drive_folder_videos(folder_id: str, access_token: str | None = None) -> list[dict]:
    folder = _extract_folder_id(folder_id)
    if not folder:
        raise DriveIntegrationError("Debes indicar un Drive folder ID o link valido")

    query = quote(f"'{folder}' in parents and trashed=false and mimeType contains 'video/'")
    fields = quote("files(id,name,mimeType,size)")

    if access_token:
        url = (
            "https://www.googleapis.com/drive/v3/files"
            f"?q={query}&fields={fields}&supportsAllDrives=true&includeItemsFromAllDrives=true"
        )
        payload = _read_json(url, access_token=access_token)
    else:
        api_key = (settings.google_api_key or "").strip()
        if not api_key:
            raise DriveIntegrationError("Falta GOOGLE_API_KEY para leer videos desde Drive")
        url = (
            "https://www.googleapis.com/drive/v3/files"
            f"?q={query}&fields={fields}&supportsAllDrives=true&includeItemsFromAllDrives=true"
            f"&key={quote(api_key)}"
        )
        payload = _read_json(url)

    files = payload.get("files") or []
    if not files:
        raise DriveIntegrationError("No se encontraron videos en la carpeta de Drive")

    return files


def download_drive_videos(folder_id: str, destination_dir: Path, oauth_token: str | None = None) -> list[Path]:
    files = list_drive_folder_videos(folder_id, access_token=oauth_token)

    destination_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    for item in files[: settings.max_drive_input_clips]:
        file_id = str(item.get("id") or "").strip()
        filename = str(item.get("name") or "video.mp4").strip() or "video.mp4"
        if not file_id:
            continue

        safe_name = Path(filename).name
        out_path = destination_dir / safe_name

        if oauth_token:
            media_url = (
                f"https://www.googleapis.com/drive/v3/files/{quote(file_id)}"
                f"?alt=media&supportsAllDrives=true"
            )
            req = Request(media_url, headers={"Authorization": f"Bearer {oauth_token}"})
        else:
            api_key = (settings.google_api_key or "").strip()
            media_url = (
                f"https://www.googleapis.com/drive/v3/files/{quote(file_id)}"
                f"?alt=media&supportsAllDrives=true&key={quote(api_key)}"
            )
            req = Request(media_url)

        with urlopen(req, timeout=120) as response:  # nosec B310
            with out_path.open("wb") as output_file:
                shutil.copyfileobj(response, output_file)

        downloaded.append(out_path)

    if not downloaded:
        raise DriveIntegrationError("No se pudo descargar ningun video desde Drive")

    return downloaded
