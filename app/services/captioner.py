from __future__ import annotations

import json
import random
from dataclasses import dataclass

from app.config import settings

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None


FALLBACK_OPENERS = [
    "POV:",
    "Si llegaste hasta aqui,",
    "No esperaba este resultado...",
    "Mira esto hasta el final:",
    "Plot twist en 20 segundos:",
]

FALLBACK_HASHTAGS = [
    "#TikTok",
    "#ParaTi",
    "#VideoCorto",
    "#Contenido",
    "#Viral",
    "#Edicion",
]


@dataclass
class GeneratedTextPack:
    overlay_text_1: str
    overlay_text_2: str
    centered_text: str
    caption: str


def _fallback_caption(seed: int, style: str, segments: int, duration: float) -> str:
    rng = random.Random(seed)
    opener = rng.choice(FALLBACK_OPENERS)
    emojis = rng.choice(["🔥", "✨", "😮", "🎬", "⚡"])
    picked_tags = " ".join(rng.sample(FALLBACK_HASHTAGS, k=4))
    return (
        f"{opener} {emojis} Version {seed}: estilo {style}, "
        f"{segments} cortes en {duration:.1f}s. {picked_tags}"
    )


def _trim_overlay(text: str, max_chars: int = 30) -> str:
    normalized = " ".join((text or "").replace("\n", " ").split())
    if not normalized:
        return ""
    return normalized[:max_chars].strip()


def _fallback_text_pack(
    variant_index: int,
    style: str,
    segments: int,
    duration: float,
    prompt_context: str,
    text_mode: str = "two_lines",
) -> GeneratedTextPack:
    rng = random.Random(variant_index * 31)
    caption = _fallback_caption(variant_index, style, segments, duration)

    if text_mode == "one_big":
        base = prompt_context.strip()[:55] if prompt_context.strip() else rng.choice([
            "No te lo pierdas",
            "Esto cambia todo",
            "Mira hasta el final",
            "Lo que nadie te cuenta",
        ])
        return GeneratedTextPack(
            overlay_text_1="",
            overlay_text_2="",
            centered_text=_trim_overlay(base, max_chars=60),
            caption=caption,
        )

    opener_base = prompt_context.strip()[:28] if prompt_context.strip() else rng.choice([
        "No te lo esperas",
        "Esto se puso bueno",
        "Mira este giro",
        "Atento al final",
    ])
    return GeneratedTextPack(
        overlay_text_1=_trim_overlay(opener_base),
        overlay_text_2=_trim_overlay(rng.choice([
            "Que opinas?",
            "Guardalo para despues",
            "Comenta tu version",
            "Mira la parte final",
        ])),
        centered_text="",
        caption=caption,
    )


def _gemini_text_pack(prompt: str, text_mode: str = "two_lines") -> GeneratedTextPack | None:
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key or genai is None:
        return None

    client = genai.Client(api_key=api_key)

    model_candidates = [
        settings.gemini_model,
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
    ]

    for model_name in model_candidates:
        if not model_name:
            continue
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            text = (response.text or "").strip()
            if text:
                cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
                payload = json.loads(cleaned)
                caption = " ".join(str(payload.get("caption") or "").split())[:220]
                if not caption:
                    continue
                if text_mode == "one_big":
                    centered = _trim_overlay(str(payload.get("centered_text") or ""), max_chars=60)
                    return GeneratedTextPack(
                        overlay_text_1="",
                        overlay_text_2="",
                        centered_text=centered,
                        caption=caption,
                    )
                return GeneratedTextPack(
                    overlay_text_1=_trim_overlay(str(payload.get("overlay_text_1") or "")),
                    overlay_text_2=_trim_overlay(str(payload.get("overlay_text_2") or "")),
                    centered_text="",
                    caption=caption,
                )
        except Exception:
            continue

    return None


def generate_text_pack(
    variant_index: int,
    style: str,
    segments: int,
    duration: float,
    prompt_context: str,
    text_mode: str = "two_lines",
) -> GeneratedTextPack:
    context = " ".join((prompt_context or "").split())[:400]

    if text_mode == "one_big":
        prompt = (
            "Genera exactamente un JSON valido sin markdown con estas llaves: "
            "centered_text, caption.\n"
            "Reglas: centered_text maximo 60 caracteres, frase impactante visible en pantalla completa durante todo el video. "
            "caption maximo 160 caracteres, estilo TikTok, con 2 emojis maximo y 3-5 hashtags. "
            "No uses saltos de linea ni comillas internas complejas.\n"
            f"Contexto del usuario: {context or 'general, dinamico, video corto'}\n"
            f"Datos: variante={variant_index}, estilo={style}, duracion={duration:.1f}s"
        )
    else:
        prompt = (
            "Genera exactamente un JSON valido sin markdown con estas llaves: "
            "overlay_text_1, overlay_text_2, caption.\n"
            "Reglas: overlay_text_1 y overlay_text_2 maximo 30 caracteres cada uno, cortos y directos para texto en pantalla. "
            "caption maximo 160 caracteres, estilo TikTok, con 2 emojis maximo y 3-5 hashtags. "
            "No uses saltos de linea ni comillas internas complejas.\n"
            f"Contexto del usuario: {context or 'general, dinamico, video corto'}\n"
            f"Datos: variante={variant_index}, estilo={style}, cortes={segments}, duracion={duration:.1f}s"
        )

    pack = _gemini_text_pack(prompt, text_mode=text_mode)
    if pack:
        return pack

    return _fallback_text_pack(variant_index, style, segments, duration, prompt_context, text_mode=text_mode)
