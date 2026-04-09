from __future__ import annotations

import json
import urllib.request

from aai_app.config import AppConfig
from aai_app.constants import DEFAULT_SUMMARY_PROMPT


def summarize_youtube_with_gemini(url: str, config: AppConfig) -> str:
    api_key = config.google_api_key.strip()
    if not api_key:
        raise RuntimeError("No Google API key is configured for YouTube fast-path summarization.")

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"file_data": {"file_uri": url}},
                        {"text": DEFAULT_SUMMARY_PROMPT},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Gemini YouTube summarization failed: {exc}") from exc

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        raise RuntimeError("Gemini did not return a YouTube summary.") from exc
