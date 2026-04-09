from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from aai_app.config import AppConfig


def detect_platform(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    raise ValueError(f"Unsupported URL host: {host or 'unknown'}")


def create_work_dir(config: AppConfig, keep_downloads: bool) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if keep_downloads:
        downloads_root = Path(config.downloads_dir).expanduser()
        downloads_root.mkdir(parents=True, exist_ok=True)
        target = downloads_root / f"job-{next(tempfile._get_candidate_names())}"
        target.mkdir(parents=True, exist_ok=True)
        return target, None
    temp_dir = tempfile.TemporaryDirectory(dir=config.cache_dir)
    return Path(temp_dir.name), temp_dir


def download_audio(url: str, config: AppConfig, work_dir: Path) -> Path:
    output_template = work_dir / "audio.%(ext)s"
    proc = subprocess.run(
        [
            config.yt_dlp_path,
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--no-playlist",
            "--ffmpeg-location",
            config.ffmpeg_path,
            "-o",
            str(output_template),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "yt-dlp failed"
        raise RuntimeError(detail)
    for candidate in work_dir.iterdir():
        if candidate.is_file() and candidate.suffix.lower() in {".mp3", ".m4a", ".wav", ".webm"}:
            return candidate
    raise RuntimeError("yt-dlp completed without producing an audio file")


def normalize_audio(input_path: Path, config: AppConfig, work_dir: Path) -> Path:
    output_path = work_dir / "audio.wav"
    proc = subprocess.run(
        [
            config.ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg normalization failed")
    return output_path
