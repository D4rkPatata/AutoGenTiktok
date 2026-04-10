from pydantic import BaseModel, Field


class GeneratedVideo(BaseModel):
    variant_index: int = Field(ge=1)
    filename: str
    download_url: str
    overlay_text_1: str
    overlay_text_2: str
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
