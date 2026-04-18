"""Google OAuth2 routes — implementación manual sin depender del estado de authlib.

Flow:
  1. GET /auth/login    → genera state, lo guarda en sesión, redirige a Google
  2. GET /auth/callback → verifica state, intercambia código por token, guarda en sesión
  3. GET /auth/me       → devuelve el usuario logueado (o 401)
  4. GET /auth/logout   → borra la sesión
"""
import json
import secrets
import time
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_SCOPES = "openid email profile https://www.googleapis.com/auth/drive.readonly"

# Estado OAuth guardado en memoria del servidor (con TTL de 10 min).
# Evita depender de que la session cookie persista durante el redirect a Google.
_pending_states: dict[str, float] = {}
_STATE_TTL = 600  # segundos


def _register_state(state: str) -> None:
    # Limpiar estados vencidos
    now = time.time()
    expired = [k for k, v in _pending_states.items() if v < now]
    for k in expired:
        del _pending_states[k]
    _pending_states[state] = now + _STATE_TTL


def _consume_state(state: str) -> bool:
    """Retorna True si el state existe y no ha vencido, y lo elimina."""
    expiry = _pending_states.pop(state, None)
    return expiry is not None and expiry > time.time()


def _http_post(url: str, data: dict) -> dict:
    body = urlencode(data).encode()
    req = UrlRequest(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=15) as resp:  # nosec B310
        return json.loads(resp.read().decode())


def _http_get_auth(url: str, token: str) -> dict:
    req = UrlRequest(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=15) as resp:  # nosec B310
        return json.loads(resp.read().decode())


@router.get("/login")
def login(request: Request):
    """Genera un state único, lo registra en memoria y redirige al consentimiento de Google."""
    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=500, detail="OAuth no configurado (faltan variables en .env)")

    state = secrets.token_urlsafe(32)
    _register_state(state)

    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Google redirige aquí. Verificamos el state, intercambiamos código y guardamos sesión."""
    if error:
        raise HTTPException(status_code=400, detail=f"Google rechazó el acceso: {error}")

    # Verificar CSRF state (guardado en memoria del servidor, no en sesión)
    if not _consume_state(state):
        raise HTTPException(status_code=400, detail="State inválido o expirado — intenta iniciar sesión de nuevo")

    if not code:
        raise HTTPException(status_code=400, detail="No se recibió código de autorización")

    # Intercambiar código por access token
    try:
        token_data = _http_post(_GOOGLE_TOKEN_URL, {
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error al obtener token: {exc}") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No se obtuvo access_token de Google")

    # Obtener info del usuario
    try:
        user_info = _http_get_auth(_GOOGLE_USERINFO_URL, access_token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error al obtener info de usuario: {exc}") from exc

    request.session["user"] = {
        "name": user_info.get("name"),
        "email": user_info.get("email"),
        "picture": user_info.get("picture"),
    }
    request.session["google_access_token"] = access_token

    return RedirectResponse(url="/")


@router.get("/me")
def me(request: Request) -> dict:
    """Devuelve el usuario logueado. Retorna 401 si no hay sesión."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user


@router.get("/logout")
def logout(request: Request):
    """Limpia la sesión y redirige al inicio."""
    request.session.clear()
    return RedirectResponse(url="/")


# ── TikTok OAuth ──────────────────────────────────────────────────────────────
_TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_TIKTOK_USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,avatar_url"
_TIKTOK_SCOPES = "user.info.basic,video.upload"

_tiktok_pending_states: dict[str, float] = {}


def _register_tiktok_state(state: str) -> None:
    now = time.time()
    expired = [k for k, v in _tiktok_pending_states.items() if v < now]
    for k in expired:
        del _tiktok_pending_states[k]
    _tiktok_pending_states[state] = now + _STATE_TTL


def _consume_tiktok_state(state: str) -> bool:
    expiry = _tiktok_pending_states.pop(state, None)
    return expiry is not None and expiry > time.time()


@router.get("/tiktok/login")
def tiktok_login(request: Request):
    if not settings.tiktok_client_key or not settings.tiktok_redirect_uri:
        raise HTTPException(status_code=500, detail="TikTok OAuth no configurado (faltan TIKTOK_CLIENT_KEY o TIKTOK_REDIRECT_URI en .env)")

    state = secrets.token_urlsafe(32)
    _register_tiktok_state(state)

    params = {
        "client_key": settings.tiktok_client_key,
        "response_type": "code",
        "scope": _TIKTOK_SCOPES,
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
    }
    return RedirectResponse(url=f"{_TIKTOK_AUTH_URL}?{urlencode(params)}")


@router.get("/tiktok/callback")
def tiktok_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=f"TikTok rechazó el acceso: {error_description or error}")

    if not _consume_tiktok_state(state):
        raise HTTPException(status_code=400, detail="State inválido o expirado — intenta conectar TikTok de nuevo")

    if not code:
        raise HTTPException(status_code=400, detail="No se recibió código de autorización de TikTok")

    try:
        token_data = _http_post(_TIKTOK_TOKEN_URL, {
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.tiktok_redirect_uri,
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error al obtener token de TikTok: {exc}") from exc

    access_token = token_data.get("access_token")
    open_id = token_data.get("open_id")
    if not access_token:
        raise HTTPException(status_code=400, detail="No se obtuvo access_token de TikTok")

    try:
        user_info = _http_get_auth(_TIKTOK_USERINFO_URL, access_token)
        user_data = user_info.get("data", {}).get("user", {})
    except Exception:
        user_data = {}

    request.session["tiktok_user"] = {
        "open_id": open_id or user_data.get("open_id", ""),
        "display_name": user_data.get("display_name", "Usuario TikTok"),
        "avatar_url": user_data.get("avatar_url", ""),
    }
    request.session["tiktok_access_token"] = access_token

    # Close the popup and notify the parent window
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head><body>
<p style="font-family:sans-serif;text-align:center;margin-top:40px">Conectado. Cerrando...</p>
<script>
  if (window.opener) {
    window.opener.postMessage("tiktok_connected", window.location.origin);
    window.close();
  } else {
    window.location.href = "/";
  }
</script>
</body></html>""")


@router.get("/tiktok/me")
def tiktok_me(request: Request) -> dict:
    user = request.session.get("tiktok_user")
    if not user:
        raise HTTPException(status_code=401, detail="No conectado a TikTok")
    return user


@router.get("/tiktok/logout")
def tiktok_logout(request: Request) -> dict:
    request.session.pop("tiktok_user", None)
    request.session.pop("tiktok_access_token", None)
    return {"ok": True}
