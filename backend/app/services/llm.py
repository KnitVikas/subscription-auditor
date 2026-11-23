"""Tiny shared OpenAI chat helper.

Centralizes the model choice (settings.openai_model) and JSON-mode request so
the parsing and enrichment agents don't each hardcode a model. Raises on failure
so callers can decide whether to fall back.
"""
from __future__ import annotations

import json

from app.core.config import settings

_URL = "https://api.openai.com/v1/chat/completions"


def chat_json(system: str, user: str, *, temperature: float | None = 0) -> dict:
    """Call the configured chat model in JSON mode and return the parsed object.

    Some models only allow the default temperature; if the request is rejected
    for that reason we retry once without it. Raises on network/HTTP/parse
    errors so the caller can fall back to a non-LLM path.
    """
    import httpx

    payload: dict = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if temperature is not None:
        payload["temperature"] = temperature

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    resp = httpx.post(_URL, headers=headers, json=payload, timeout=30)
    if (
        resp.status_code == 400
        and "temperature" in payload
        and "temperature" in resp.text
    ):
        payload.pop("temperature")
        resp = httpx.post(_URL, headers=headers, json=payload, timeout=30)

    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)
