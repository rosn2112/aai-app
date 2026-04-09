from __future__ import annotations

from pathlib import Path

from aai_app.adapters.base import Summarizer
from aai_app.config import AppConfig
from aai_app.rendering import clean_model_output


class MLXSummarizer(Summarizer):
    name = "mlx"

    def __init__(self, config: AppConfig) -> None:
        model_path = Path(config.mlx_model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"MLX model is missing at {model_path}")
        from mlx_lm import generate, load, stream_generate

        self._generate = generate
        self._stream_generate = stream_generate
        self._model, self._tokenizer = load(str(model_path))

    def _run_prompt(self, prompt: str) -> str:
        return clean_model_output(self._generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            verbose=False,
            max_tokens=256,
        ).strip())

    def _chat_prompt(self, messages: list[dict[str, str]], system_prompt: str) -> str:
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(messages)
        if hasattr(self._tokenizer, "apply_chat_template"):
            rendered = self._tokenizer.apply_chat_template(
                conversation,
                tokenize=False,
                add_generation_prompt=True,
            )
            return str(rendered)
        prompt_parts = [system_prompt.strip(), ""]
        for message in messages:
            role = message["role"].capitalize()
            prompt_parts.append(f"{role}: {message['content'].strip()}")
        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)

    def _stream_prompt(self, prompt: str):
        chunks: list[str] = []
        for response in self._stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=256,
        ):
            chunk = response.text or ""
            if chunk:
                chunks.append(chunk)
                cleaned = clean_model_output("".join(chunks))
                if cleaned != "(no response)":
                    yield {"content": cleaned, "thinking": ""}

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        return self._run_prompt(self._chat_prompt(messages, system_prompt))

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ):
        yield from self._stream_prompt(self._chat_prompt(messages, system_prompt))

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
