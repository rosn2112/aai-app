from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from aai_app.adapters import build_summarizer
from aai_app.config import AppConfig
from aai_app.constants import DEFAULT_SUMMARY_PROMPT, DEFAULT_TRANSCRIPT_CORRECTION_PROMPT
from aai_app.core.media import create_work_dir, detect_platform, download_audio, normalize_audio
from aai_app.core.transcribe import transcribe_audio
from aai_app.doctor import get_chat_blockers, get_media_blockers, run_doctor
from aai_app.rendering import clean_model_output
from aai_app.core.youtube_api import summarize_youtube_with_gemini


@dataclass
class SummaryResult:
    platform: str
    url: str
    backend: str
    transcript: str
    corrected_transcript: str
    summary: str
    kept_downloads: bool
    artifact_dir: str | None = None


def correct_transcript(raw_transcript: str, config: AppConfig) -> tuple[str, str]:
    summarizer = build_summarizer(config)
    correction_request = (
        f"{DEFAULT_TRANSCRIPT_CORRECTION_PROMPT}\n\n"
        f"Transcript:\n{raw_transcript}"
    )
    corrected = clean_model_output(
        summarizer.chat(
            [{"role": "user", "content": correction_request}],
            "You correct Hindi and Sanskrit transcripts for readability and accuracy.",
        )
    )
    return summarizer.name, corrected


def summarize_url(
    command_name: str,
    url: str,
    config: AppConfig,
    console: Console,
    keep_downloads: bool = False,
) -> SummaryResult:
    check_map = {check.name: check for check in run_doctor(config)}
    platform_name = detect_platform(url)
    expected = {
        "/youtube": "youtube",
        "/instagram": "instagram",
    }.get(command_name, command_name.removeprefix("/"))
    if expected != platform_name:
        raise ValueError(f"{command_name} does not support {platform_name} URLs")

    youtube_mode = config.youtube_mode.strip().lower()
    if platform_name == "youtube" and config.google_api_key.strip() and youtube_mode in {"auto", "gemini"}:
        with console.status("Summarizing YouTube with Gemini...", spinner="dots"):
            summary = summarize_youtube_with_gemini(url, config)
        return SummaryResult(
            platform=platform_name,
            url=url,
            backend="gemini-api",
            transcript="",
            corrected_transcript="",
            summary=summary,
            kept_downloads=False,
            artifact_dir=None,
        )

    blockers = get_media_blockers(check_map, config.inference_mode)
    if blockers:
        detail = "\n".join(f"- {item}" for item in blockers)
        raise RuntimeError(
            "AAI App is not ready yet.\n"
            f"{detail}\n"
            "Run `/doctor` to inspect the environment and re-run `./install.sh` if needed."
        )

    work_dir, temp_dir = create_work_dir(config, keep_downloads=keep_downloads)
    try:
        with console.status("Downloading media...", spinner="dots"):
            downloaded = download_audio(url, config, work_dir)
        with console.status("Normalizing audio...", spinner="dots"):
            audio_path = normalize_audio(downloaded, config, work_dir)
        with console.status("Transcribing with Whisper...", spinner="dots"):
            transcript = transcribe_audio(audio_path, config)
        with console.status("Correcting transcript for Hindi/Sanskrit terms...", spinner="dots"):
            backend_name, corrected_transcript = correct_transcript(transcript, config)
        with console.status("Summarizing with Ollama...", spinner="dots"):
            summarizer = build_summarizer(config)
            summary = clean_model_output(summarizer.summarize(corrected_transcript, DEFAULT_SUMMARY_PROMPT))
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
    return SummaryResult(
        platform=platform_name,
        url=url,
        backend=backend_name,
        transcript=transcript,
        corrected_transcript=corrected_transcript,
        summary=summary,
        kept_downloads=keep_downloads,
        artifact_dir=str(work_dir) if keep_downloads else None,
    )
