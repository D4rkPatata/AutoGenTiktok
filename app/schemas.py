from pydantic import BaseModel, Field


class GeneratedVideo(BaseModel):
    variant_index: int = Field(ge=1)
    filename: str
    download_url: str
    overlay_text_1: str
    overlay_text_2: str
    centered_text: str = ""
    caption: str


class GenerateResponse(BaseModel):
    job_id: str
    style: str
    requested_versions: int
    generated_versions: int
    results: list[GeneratedVideo]


class MusicPreset(BaseModel):
    name: str
    filename: str
    trend_tag: str = "general"


class ZipRequest(BaseModel):
    filenames: list[str] = Field(default_factory=list)


class TiktokDraftRequest(BaseModel):
    filenames: list[str] = Field(default_factory=list)
    captions: dict[str, str] = Field(default_factory=dict)  # filename → caption


class TiktokConnectionStatus(BaseModel):
    connected: bool
    message: str


class TiktokDraftResult(BaseModel):
    filename: str
    ok: bool
    message: str


class TiktokDraftResponse(BaseModel):
    sent: int
    attempted: int
    results: list[TiktokDraftResult]
