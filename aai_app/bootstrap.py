from __future__ import annotations

import argparse
import subprocess
import shutil
import stat
import sys
from pathlib import Path

from rich.console import Console

from aai_app.config import load_config


def bootstrap(app_home: str | None = None) -> None:
    bootstrap_with_options(app_home=app_home)


def _ollama_model_installed(ollama_bin: str, model_name: str) -> bool:
    result = subprocess.run(
        [ollama_bin, "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return any(line.split()[0] == model_name for line in lines[1:])


def _ensure_yt_dlp(config, console: Console) -> str:
    venv_bin = Path(sys.executable).resolve().parent
    direct_binary = shutil.which("yt-dlp") or str(venv_bin / "yt-dlp")
    if direct_binary and Path(direct_binary).exists():
        return direct_binary

    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is not installed in the active environment. "
            "Rerun `./install.sh` so it can install the runtime dependencies into the app venv."
        ) from exc

    shim_path = config.bin_dir / "yt-dlp"
    shim_path.write_text(
        "#!/usr/bin/env bash\n"
        f"exec \"{sys.executable}\" -m yt_dlp \"$@\"\n"
    )
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IEXEC)
    console.print(f"Created yt-dlp launcher shim at {shim_path}")
    return str(shim_path)


def bootstrap_with_options(
    app_home: str | None = None,
    inference_mode: str | None = None,
    google_api_key: str | None = None,
    install_local_models: bool | None = None,
) -> None:
    console = Console()
    config = load_config(app_home)
    config.ensure_directories()
    warnings: list[str] = []

    if inference_mode:
        config.inference_mode = inference_mode
    if google_api_key is not None:
        config.google_api_key = google_api_key.strip()

    try:
        import imageio_ffmpeg
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Runtime dependencies are not installed. Run `pip install -e '.[runtime]'` "
            "or use `./install.sh` for the full setup."
        ) from exc

    config.yt_dlp_path = _ensure_yt_dlp(config, console)

    ffmpeg_source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    ffmpeg_target = config.bin_dir / "ffmpeg"
    if not ffmpeg_target.exists():
        shutil.copy2(ffmpeg_source, ffmpeg_target)
        ffmpeg_target.chmod(ffmpeg_target.stat().st_mode | stat.S_IEXEC)
    config.ffmpeg_path = str(ffmpeg_target)

    console.print("Caching Whisper model...")
    WhisperModel(
        config.whisper_model_name,
        device="cpu",
        compute_type="int8",
        download_root=config.whisper_download_root,
    )

    if config.inference_mode == "ollama":
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            raise RuntimeError("Ollama CLI is not installed. Install Ollama to use the default local backend.")

        if _ollama_model_installed(ollama_bin, config.ollama_model):
            console.print(f"Ollama model already installed: {config.ollama_model}")
        else:
            console.print(f"Ensuring Ollama model is installed: {config.ollama_model}")
            try:
                subprocess.run([ollama_bin, "pull", config.ollama_model], check=True)
            except Exception as exc:
                raise RuntimeError(
                    "Ollama model pull failed. Run `ollama pull "
                    f"{config.ollama_model}` manually, then rerun `./install.sh`.\n"
                    f"Original error: {exc}"
                ) from exc
    console.print("Skipping bundled local LLM downloads. Ollama is the only local runtime.")

    config.save()
    console.print(f"Bootstrap complete. Config saved to {config.config_path}")
    for warning in warnings:
        console.print(f"Warning: {warning}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-home", default=None)
    parser.add_argument("--inference-mode", choices=["ollama"], default=None)
    parser.add_argument("--google-api-key", default=None)
    args = parser.parse_args()
    bootstrap_with_options(
        app_home=args.app_home,
        inference_mode=args.inference_mode,
        google_api_key=args.google_api_key,
    )


if __name__ == "__main__":
    main()
