from __future__ import annotations

from pathlib import Path

from aai_app.config import AppConfig


def transcribe_audio(audio_path: Path, config: AppConfig) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel(
        config.whisper_model_name,
        device="cpu",
        compute_type="int8",
        download_root=config.whisper_download_root,
    )
    segments, _ = model.transcribe(str(audio_path), beam_size=1, vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise RuntimeError("Whisper produced an empty transcript")
    return text

