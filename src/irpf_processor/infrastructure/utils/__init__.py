"""Utilitários gerais (migrados de doc-extractor)."""

import base64
import mimetypes


# MIME types que o GPT-4o aceita diretamente como imagem
IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def guess_mime(filename: str) -> str:
    """Adivinha o MIME type de um arquivo pelo nome."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def make_image_content(image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """Cria um content block de imagem para a API do OpenAI."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{b64}",
            "detail": "high",
        },
    }
