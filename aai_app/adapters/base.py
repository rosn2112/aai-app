from __future__ import annotations

from abc import ABC, abstractmethod


class Summarizer(ABC):
    name: str

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, transcript: str, prompt: str) -> str:
        raise NotImplementedError

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ):
        yield {"content": self.chat(messages, system_prompt), "thinking": ""}

    def stream_summarize(self, transcript: str, prompt: str):
        yield {"content": self.summarize(transcript, prompt), "thinking": ""}
