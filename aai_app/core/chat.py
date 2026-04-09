from __future__ import annotations

from rich.console import Console

from aai_app.adapters import build_summarizer
from aai_app.config import AppConfig
from aai_app.doctor import get_chat_blockers, run_doctor
from aai_app.rendering import clean_model_output

CHAT_SYSTEM_PROMPT = (
    "You are AAI App, a local-first assistant running in a terminal. "
    "Be concise, practical, and clear. Use plain text suitable for a CLI. "
    "Keep answers structured when useful, but do not use markdown tables. "
    "Return only the next assistant reply. Do not include User:, Assistant:, or conversation transcripts."
)


def chat_with_local_model(
    user_message: str,
    conversation: list[dict[str, str]],
    config: AppConfig,
    console: Console,
) -> tuple[str, str]:
    check_map = {check.name: check for check in run_doctor(config)}
    blockers = get_chat_blockers(check_map, config.inference_mode)
    if blockers:
        detail = "\n".join(f"- {item}" for item in blockers)
        raise RuntimeError(
            "AAI App is not ready for local chat.\n"
            f"{detail}\n"
            "Run `/doctor` to inspect the environment and re-run `./install.sh` if needed."
        )

    messages = [*conversation, {"role": "user", "content": user_message}]
    with console.status("Thinking locally...", spinner="dots"):
        summarizer = build_summarizer(config)
        reply = summarizer.chat(messages, CHAT_SYSTEM_PROMPT)
    return summarizer.name, clean_model_output(reply)


def stream_chat_with_local_model(
    user_message: str,
    conversation: list[dict[str, str]],
    config: AppConfig,
):
    check_map = {check.name: check for check in run_doctor(config)}
    blockers = get_chat_blockers(check_map, config.inference_mode)
    if blockers:
        detail = "\n".join(f"- {item}" for item in blockers)
        raise RuntimeError(
            "AAI App is not ready for local chat.\n"
            f"{detail}\n"
            "Run `/doctor` to inspect the environment and re-run `./install.sh` if needed."
        )
    messages = [*conversation, {"role": "user", "content": user_message}]
    summarizer = build_summarizer(config)
    for chunk in summarizer.stream_chat(messages, CHAT_SYSTEM_PROMPT):
        if isinstance(chunk, dict):
            content = clean_model_output(chunk.get("content", "")) if chunk.get("content", "") else ""
            thinking = chunk.get("thinking", "").strip()
            yield summarizer.name, content, thinking
        else:
            yield summarizer.name, clean_model_output(chunk), ""
