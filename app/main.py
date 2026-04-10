from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.services.storage import ensure_base_dirs, cleanup_old_jobs


app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
app.mount("/", StaticFiles(directory="frontend/static", html=True), name="frontend")


@app.on_event("startup")
def startup() -> None:
    ensure_base_dirs()
    cleanup_old_jobs()
