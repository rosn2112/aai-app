from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from aai_app.constants import (
    DEFAULT_APP_HOME,
    DEFAULT_API_BASE_URL,
    DEFAULT_API_MODEL,
    DEFAULT_BACKEND_ORDER,
    DEFAULT_INFERENCE_MODE,
    DEFAULT_LLAMA_MODEL_FILE,
    DEFAULT_LLAMA_MODEL_REPO,
    DEFAULT_MLX_MODEL_REPO,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_YOUTUBE_MODE,
)


@dataclass
class AppConfig:
    app_home: str = str(DEFAULT_APP_HOME)
    inference_mode: str = DEFAULT_INFERENCE_MODE
    backend_order: list[str] = field(default_factory=lambda: list(DEFAULT_BACKEND_ORDER))
    api_base_url: str = DEFAULT_API_BASE_URL
    api_key: str = ""
    api_model: str = DEFAULT_API_MODEL
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    google_api_key: str = ""
    youtube_mode: str = DEFAULT_YOUTUBE_MODE
    whisper_model_name: str = DEFAULT_WHISPER_MODEL
    whisper_download_root: str = ""
    yt_dlp_path: str = ""
    ffmpeg_path: str = ""
    downloads_dir: str = ""
    show_thinking: bool = False
    mlx_model_repo: str = DEFAULT_MLX_MODEL_REPO
    mlx_model_path: str = ""
    llama_cpp_bin: str = ""
    llama_model_repo: str = DEFAULT_LLAMA_MODEL_REPO
    llama_model_file: str = DEFAULT_LLAMA_MODEL_FILE
    llama_model_path: str = ""

    @property
    def home_path(self) -> Path:
        return Path(self.app_home).expanduser()

    @property
    def config_path(self) -> Path:
        return self.home_path / "config.json"

    @property
    def models_dir(self) -> Path:
        return self.home_path / "models"

    @property
    def cache_dir(self) -> Path:
        return self.home_path / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.home_path / "logs"

    @property
    def bin_dir(self) -> Path:
        return self.home_path / "bin"

    @property
    def integrations_path(self) -> Path:
        return self.home_path / "mcp_servers.json"

    def ensure_directories(self) -> None:
        for path in [
            self.home_path,
            self.models_dir,
            self.cache_dir,
            self.logs_dir,
            self.bin_dir,
            self.models_dir / "mlx",
            self.models_dir / "llama.cpp",
            self.models_dir / "whisper",
            Path(self.downloads_dir).expanduser() if self.downloads_dir else self.home_path / "downloads",
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.ensure_directories()
        self.config_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def load_config(app_home: str | Path | None = None) -> AppConfig:
    home = Path(app_home).expanduser() if app_home else DEFAULT_APP_HOME
    config_path = home / "config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        config = AppConfig(**data)
        changed = False
        if not config.downloads_dir:
            config.downloads_dir = str(Path.home() / "Downloads" / "aai-app" / "downloadedContent")
            changed = True
        if config.backend_order != list(DEFAULT_BACKEND_ORDER):
            config.backend_order = list(DEFAULT_BACKEND_ORDER)
            changed = True
        if config.inference_mode != DEFAULT_INFERENCE_MODE:
            config.inference_mode = DEFAULT_INFERENCE_MODE
            changed = True
        if not config.ollama_base_url:
            config.ollama_base_url = DEFAULT_OLLAMA_BASE_URL
            changed = True
        if not config.ollama_model:
            config.ollama_model = DEFAULT_OLLAMA_MODEL
            changed = True
        if config.ollama_model in {"qwen3:4b", "hf.co/unsloth/gemma-4-E4B-it-GGUF:Q6_K"}:
            config.ollama_model = DEFAULT_OLLAMA_MODEL
            changed = True
        if config.api_model == "google/gemini-2.5-flash-preview":
            config.api_model = DEFAULT_API_MODEL
            changed = True
        if config.llama_model_repo == "bartowski/google_gemma-3-4b-it-GGUF":
            config.llama_model_repo = DEFAULT_LLAMA_MODEL_REPO
            changed = True
        if config.llama_model_file in {
            "google_gemma-3-4b-it-Q4_K_M.gguf",
            "gemma-4-E4B-it-Q4_K_M.gguf",
        }:
            config.llama_model_file = DEFAULT_LLAMA_MODEL_FILE
            config.llama_model_path = str(config.models_dir / "llama.cpp" / config.llama_model_file)
            changed = True
        if changed:
            config.save()
    else:
        config = AppConfig(app_home=str(home))
        config.ensure_directories()
        config.whisper_download_root = str(config.models_dir / "whisper")
        config.mlx_model_path = str(config.models_dir / "mlx" / "gemma")
        config.llama_model_path = str(config.models_dir / "llama.cpp" / config.llama_model_file)
        config.downloads_dir = str(Path.home() / "Downloads" / "aai-app" / "downloadedContent")
        config.save()
    config.ensure_directories()
    return config
