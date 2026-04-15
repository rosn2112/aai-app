from __future__ import annotations

import json
import platform
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from aai_app.config import AppConfig


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    detail: str


@dataclass
class RuntimeStatus:
    checks: list[DoctorCheck]
    ready: bool
    blocking_items: list[str]


def _has_files(path: str) -> bool:
    candidate = Path(path)
    if not candidate.exists():
        return False
    if candidate.is_file():
        return True
    return any(item.is_file() for item in candidate.rglob("*"))


def _ollama_status(config: AppConfig) -> tuple[bool, str]:
    base_url = config.ollama_base_url.rstrip("/")
    try:
        request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return False, f"{base_url} unavailable: {exc}"
    models = {item.get("name", "") for item in payload.get("models", [])}
    if config.ollama_model.strip() in models:
        return True, f"{config.ollama_model} via {base_url}"
    return False, f"{config.ollama_model or 'missing model'} not found at {base_url}"


def list_ollama_models(config: AppConfig) -> list[str]:
    base_url = config.ollama_base_url.rstrip("/")
    request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]


def run_doctor(config: AppConfig) -> list[DoctorCheck]:
    ollama_ok, ollama_detail = _ollama_status(config)
    checks = [
        DoctorCheck("platform", platform.system() == "Darwin", platform.platform()),
        DoctorCheck("inference-mode", config.inference_mode == "ollama", config.inference_mode),
        DoctorCheck(
            "google-api-key",
            bool(config.google_api_key.strip()),
            "configured" if config.google_api_key.strip() else "missing",
        ),
        DoctorCheck("ollama-model", ollama_ok, ollama_detail),
        DoctorCheck("yt-dlp", Path(config.yt_dlp_path).exists(), config.yt_dlp_path or "missing"),
        DoctorCheck("ffmpeg", Path(config.ffmpeg_path).exists(), config.ffmpeg_path or "missing"),
        DoctorCheck(
            "whisper-cache",
            _has_files(config.whisper_download_root),
            config.whisper_download_root or "missing",
        ),
    ]
    return checks


def get_runtime_status(config: AppConfig) -> RuntimeStatus:
    checks = run_doctor(config)
    check_map = {check.name: check for check in checks}
    blocking_items = get_media_blockers(check_map, config.inference_mode)
    return RuntimeStatus(checks=checks, ready=not blocking_items, blocking_items=blocking_items)


def _local_backend_ready(check_map: dict[str, DoctorCheck]) -> bool:
    return check_map["ollama-model"].ok


def get_chat_blockers(check_map: dict[str, DoctorCheck], inference_mode: str = "ollama") -> list[str]:
    blockers: list[str] = []
    if not check_map["platform"].ok:
        blockers.append("macOS is required for this version of AAI App.")
    if not _local_backend_ready(check_map):
        blockers.append("The configured Ollama model is not ready.")
    return blockers


def get_media_blockers(check_map: dict[str, DoctorCheck], inference_mode: str = "ollama") -> list[str]:
    blockers = get_chat_blockers(check_map, inference_mode)
    if not check_map["yt-dlp"].ok:
        blockers.append("`yt-dlp` is missing.")
    if not check_map["ffmpeg"].ok:
        blockers.append("`ffmpeg` is missing.")
    if not check_map["whisper-cache"].ok:
        blockers.append("Whisper model files are not installed yet.")
    return blockers
