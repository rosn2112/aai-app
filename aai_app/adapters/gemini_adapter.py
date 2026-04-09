from __future__ import annotations

import json
import urllib.request

from aai_app.adapters.base import Summarizer
from aai_app.config import AppConfig


class GeminiSummarizer(Summarizer):
    name = "gemini-api"

    def __init__(self, config: AppConfig) -> None:
        self._api_key = config.google_api_key.strip()
        self._model = "gemini-2.5-flash"
        if not self._api_key:
            raise RuntimeError("Gemini mode requires a Google API key.")

    def _request(self, contents: list[dict[str, object]]) -> str:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        payload = json.dumps(
            {
                "contents": contents,
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
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "\n".join(part.get("text", "") for part in parts).strip()
        except Exception as exc:
            raise RuntimeError("Gemini response did not contain text output.") from exc

    def chat(self, messages: list[dict[str, str]], system_prompt: str) -> str:
        transcript = [system_prompt, ""]
        for message in messages:
            role = message.get("role", "user").upper()
            content = message.get("content", "").strip()
            if content:
                transcript.append(f"{role}: {content}")
        contents = [{"parts": [{"text": "\n".join(transcript).strip()}]}]
        return self._request(contents)

    def summarize(self, transcript: str, prompt: str) -> str:
        contents = [
            {
                "parts": [
                    {
                        "text": (
                            "You summarize transcripts clearly and concisely.\n\n"
                            f"{prompt}\n\nTranscript:\n{transcript}\n\n"
                            "Return only the summary in plain text."
                        )
                    }
                ]
            }
        ]
        return self._request(contents)
