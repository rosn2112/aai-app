from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path

from aai_app.adapters.base import Summarizer
from aai_app.config import AppConfig
from aai_app.rendering import clean_model_output


class LlamaCppSummarizer(Summarizer):
    name = "llama.cpp"

    def __init__(self, config: AppConfig) -> None:
        self._binary = Path(config.llama_cpp_bin)
        self._model = Path(config.llama_model_path)
        if not self._binary.exists():
            raise FileNotFoundError(f"llama.cpp binary is missing at {self._binary}")
        if not self._model.exists():
            raise FileNotFoundError(f"llama.cpp model is missing at {self._model}")

    def _base_args(self, prompt: str) -> list[str]:
        args = [
            str(self._binary),
            "-m",
            str(self._model),
            "-p",
            prompt,
            "-n",
            "256",
            "--temp",
            "0",
            "--no-display-prompt",
            "--ctx-size",
            "4096",
            "--single-turn",
            "--simple-io",
            "--log-disable",
            "--color",
            "off",
        ]
        if sys.platform == "darwin":
            args.extend([
                "--device",
                "MTL0",
                "--gpu-layers",
                "999",
                "--main-gpu",
                "0",
                "--op-offload",
            ])
        return args

    def _sanitize_output(self, raw: str, prompt: str) -> str:
        text = raw.replace("\r", "")
        text = re.sub(r".\x08", "", text)
        if "\n> " in text:
            text = text.split("\n> ", 1)[1]
        text = text.replace(prompt, "", 1)
        if "\n> " in text:
            text = text.split("\n> ", 1)[-1]
        if "[End thinking]" in text:
            text = text.split("[End thinking]", 1)[-1]
        text = re.sub(r"\[ Prompt:.*?\]\n?", "", text, flags=re.DOTALL)
        text = text.replace("Exiting...", "")
        text = re.sub(r"Loading model\.\.\.\s*", "", text)
        text = text.replace("using custom system prompt\n", "")
        lines = [line.strip() for line in text.splitlines()]
        lines = [
            line
            for line in lines
            if line
            and not line.startswith("> ")
            and line != "[Start thinking]"
            and line != "[End thinking]"
            and line != "Thinking Process:"
            and not line.startswith("available commands:")
            and not line.startswith("/exit or Ctrl+C")
            and not line.startswith("/regen")
            and not line.startswith("/clear")
            and not line.startswith("/read <file>")
            and not line.startswith("/glob <pattern>")
            and not line.startswith("build      :")
            and not line.startswith("model      :")
            and not line.startswith("modalities :")
            and "██" not in line
            and "▄▄" not in line
        ]
        cleaned = "\n".join(lines).strip()
        return clean_model_output(cleaned)

    def _run_prompt(self, prompt: str) -> str:
        proc = subprocess.run(
            self._base_args(prompt),
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "llama.cpp failed to summarize")
        return self._sanitize_output(proc.stdout, prompt)

    def _stream_prompt(self, prompt: str):
        yield {"content": self._run_prompt(prompt), "thinking": ""}

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        prompt_parts = [system_prompt.strip(), ""]
        for message in messages:
            role = message["role"].capitalize()
            prompt_parts.append(f"{role}: {message['content'].strip()}")
        prompt_parts.append("Assistant:")
        return self._run_prompt("\n".join(prompt_parts))

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ):
        prompt_parts = [system_prompt.strip(), ""]
        for message in messages:
            role = message["role"].capitalize()
            prompt_parts.append(f"{role}: {message['content'].strip()}")
        prompt_parts.append("Assistant:")
        yield from self._stream_prompt("\n".join(prompt_parts))

    def summarize(self, transcript: str, prompt: str) -> str:
        full_prompt = (
            f"{prompt}\n\nTranscript:\n{transcript}\n\n"
            "Return only the summary in plain text."
        )
        return self._run_prompt(full_prompt)

    def stream_summarize(self, transcript: str, prompt: str):
        full_prompt = (
            f"{prompt}\n\nTranscript:\n{transcript}\n\n"
            "Return only the summary in plain text."
        )
        yield from self._stream_prompt(full_prompt)
