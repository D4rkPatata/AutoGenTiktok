from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GenVideosAuto"
    api_prefix: str = "/api"

    workspace_dir: Path = Path("data")
    jobs_dir_name: str = "jobs"
    music_presets_dir_name: str = "music_presets"
    ending_clip_path: Path = Path("data/logo/ending.mp4")

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    max_input_clips: int = 10
    max_output_versions: int = 10
    max_clip_size_mb: int = 150
    max_music_size_mb: int = 30

    target_width: int = 1080
    target_height: int = 1920
    target_fps: int = 30
    default_target_duration_sec: float = 22.0

    cleanup_after_hours: int = 24

    # Optional: Google Gemini free tier key.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Optional: Google Drive source integration.
    google_api_key: str | None = None
    max_drive_input_clips: int = 10

    # Optional: TikTok draft integration (manual token).
    tiktok_access_token: str | None = None
    tiktok_open_id: str | None = None
    tiktok_draft_endpoint: str = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    # TikTok OAuth2 (Login Kit).
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_redirect_uri: str | None = None

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None
    session_secret: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
