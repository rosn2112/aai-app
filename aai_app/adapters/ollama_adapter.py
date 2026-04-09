from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from aai_app.adapters.base import Summarizer
from aai_app.config import AppConfig
from aai_app.rendering import clean_model_output


class OllamaSummarizer(Summarizer):
    name = "ollama"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._base_url = config.ollama_base_url.rstrip("/")
        self._model = config.ollama_model.strip()
        if not self._model:
            raise RuntimeError("Ollama mode is enabled but no Ollama model is configured.")
        self._ensure_model_available()

    def _tags_payload(self) -> dict:
        request = urllib.request.Request(f"{self._base_url}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _start_ollama_server(self) -> None:
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            raise RuntimeError("Ollama is not installed or not on PATH.")
        log_path = Path(self._config.logs_dir) / "ollama-serve.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_file:
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

    def _wait_for_ollama(self) -> dict:
        deadline = time.time() + 12
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                return self._tags_payload()
            except Exception as exc:
                last_exc = exc
                time.sleep(0.5)
        raise RuntimeError(f"Ollama is not reachable at {self._base_url}: {last_exc}") from last_exc

    def _ensure_model_available(self) -> None:
        try:
            payload = self._tags_payload()
        except Exception as exc:
            self._start_ollama_server()
            payload = self._wait_for_ollama()
        models = {item.get("name", "") for item in payload.get("models", [])}
        if self._model not in models:
            raise RuntimeError(f"Ollama model `{self._model}` is not installed.")

    def _chat_request(self, messages: list[dict[str, str]], stream: bool):
        payload = json.dumps(
            {
                "model": self._model,
                "messages": messages,
                "stream": stream,
                "think": bool(self._config.show_thinking),
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=300)

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        payload = [{"role": "system", "content": system_prompt}, *messages]
        try:
            with self._chat_request(payload, stream=False) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        message = data.get("message", {}).get("content", "")
        return clean_model_output(message)

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ):
        payload = [{"role": "system", "content": system_prompt}, *messages]
        accumulated = ""
        thinking = ""
        try:
            with self._chat_request(payload, stream=True) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    accumulated += message.get("content", "")
                    thinking += message.get("thinking", "")
                    if accumulated or thinking:
                        yield {
                            "content": clean_model_output(accumulated) if accumulated else "",
                            "thinking": thinking.strip(),
                        }
        except Exception as exc:
            raise RuntimeError(f"Ollama streaming request failed: {exc}") from exc

    def summarize(self, transcript: str, prompt: str) -> str:
        message = (
            f"{prompt}\n\nTranscript:\n{transcript}\n\n"
            "Return only the summary in plain text."
        )
        return self.chat([{"role": "user", "content": message}], "You summarize transcripts clearly and concisely.")

    def stream_summarize(self, transcript: str, prompt: str):
        message = (
            f"{prompt}\n\nTranscript:\n{transcript}\n\n"
            "Return only the summary in plain text."
        )
        yield from self.stream_chat(
            [{"role": "user", "content": message}],
            "You summarize transcripts clearly and concisely.",
        )
