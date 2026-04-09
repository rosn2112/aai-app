from __future__ import annotations

from aai_app.adapters.api_adapter import APISummarizer
from aai_app.adapters.base import Summarizer
from aai_app.adapters.gemini_adapter import GeminiSummarizer
from aai_app.config import AppConfig


class ResilientRemoteSummarizer(Summarizer):
    name = "remote-api"

    def __init__(self, config: AppConfig) -> None:
        self._primary: Summarizer | None = None
        self._fallback: Summarizer | None = None

        if config.api_key.strip():
            self._primary = APISummarizer(config)
        if config.google_api_key.strip():
            self._fallback = GeminiSummarizer(config)

        if self._primary is None and self._fallback is None:
            raise RuntimeError("No remote API backend is configured.")

        if self._primary is None:
            self.name = "gemini-api"
        elif self._fallback is None:
            self.name = self._primary.name

    def _run(self, method_name: str, *args: object) -> str:
        if self._primary is not None:
            try:
                return getattr(self._primary, method_name)(*args)
            except Exception as exc:
                if self._fallback is None:
                    raise
                fallback_name = self._fallback.name
                self.name = f"{fallback_name} (fallback)"
        if self._fallback is None:
            raise RuntimeError("No fallback API backend is configured.")
        return getattr(self._fallback, method_name)(*args)

    def chat(self, messages: list[dict[str, str]], system_prompt: str) -> str:
        return self._run("chat", messages, system_prompt)

    def summarize(self, transcript: str, prompt: str) -> str:
        return self._run("summarize", transcript, prompt)
