from __future__ import annotations

import json
import urllib.request

from aai_app.config import AppConfig


def fetch_openrouter_models(config: AppConfig) -> list[dict[str, str]]:
    api_key = config.api_key.strip()
    if not api_key:
        raise RuntimeError("No OpenRouter API key is configured.")

    request = urllib.request.Request(
        f"{config.api_base_url.rstrip('/')}/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "AAI App",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Unable to fetch remote model list: {exc}") from exc

    models = payload.get("data", [])
    result: list[dict[str, str]] = []
    for item in models:
        result.append(
            {
                "id": str(item.get("id", "")),
                "name": str(item.get("name", "")),
                "pricing": str(item.get("pricing", {}).get("prompt", "")),
                "completion_pricing": str(item.get("pricing", {}).get("completion", "")),
                "context_length": str(item.get("context_length", "")),
            }
        )
    return result


def is_free_model(model: dict[str, str]) -> bool:
    prompt_price = (model.get("pricing") or "").strip()
    completion_price = (model.get("completion_pricing") or "").strip()
    return prompt_price == "0" and completion_price == "0"


def fetch_openrouter_free_models(config: AppConfig) -> list[dict[str, str]]:
    return [model for model in fetch_openrouter_models(config) if is_free_model(model)]
