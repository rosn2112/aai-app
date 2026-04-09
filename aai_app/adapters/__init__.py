from aai_app.adapters.base import Summarizer
from aai_app.adapters.ollama_adapter import OllamaSummarizer
from aai_app.config import AppConfig

_SUMMARIZER_CACHE: dict[tuple[str, ...], Summarizer] = {}


def _cache_key(config: AppConfig) -> tuple[str, ...]:
    return (
        config.ollama_base_url.strip(),
        config.ollama_model.strip(),
    )


def build_summarizer(config: AppConfig) -> Summarizer:
    key = _cache_key(config)
    cached = _SUMMARIZER_CACHE.get(key)
    if cached is not None:
        return cached
    summarizer = OllamaSummarizer(config)
    _SUMMARIZER_CACHE[key] = summarizer
    return summarizer
