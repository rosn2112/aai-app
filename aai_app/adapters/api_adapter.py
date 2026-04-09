from __future__ import annotations

import json
import urllib.request

from aai_app.adapters.base import Summarizer
from aai_app.config import AppConfig


class APISummarizer(Summarizer):
    name = "api"

    def __init__(self, config: AppConfig) -> None:
        self._base_url = config.api_base_url.rstrip("/")
        self._api_key = config.api_key.strip()
        self._model = config.api_model.strip()
        if not self._api_key:
            raise RuntimeError("API mode is enabled but no API key is configured.")
        if not self._model:
            raise RuntimeError("API mode is enabled but no API model is configured.")

    def _request(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {
                "model": self._model,
                "messages": messages,
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "http://localhost",
                "X-Title": "AAI App",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"API request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise RuntimeError("API response did not contain a chat completion.") from exc

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        payload = [{"role": "system", "content": system_prompt}, *messages]
        return self._request(payload)

    def summarize(self, transcript: str, prompt: str) -> str:
        payload = [
            {"role": "system", "content": "You summarize transcripts clearly and concisely."},
            {
                "role": "user",
                "content": f"{prompt}\n\nTranscript:\n{transcript}\n\nReturn only the summary in plain text.",
            },
        ]
        return self._request(payload)
