from __future__ import annotations

import re

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


def clean_model_output(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").strip()
    assistant_markers = [
        "\nAssistant:",
        "Assistant:",
        "\nASSISTANT:",
        "ASSISTANT:",
    ]
    for marker in assistant_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[-1].strip()
    stop_markers = [
        "\nUser:",
        "\nUSER:",
        "\nSystem:",
        "\nSYSTEM:",
        "\nAssistant:",
        "\nASSISTANT:",
    ]
    stop_positions = [cleaned.find(marker) for marker in stop_markers if cleaned.find(marker) > 0]
    if stop_positions:
        cleaned = cleaned[: min(stop_positions)].strip()
    cleaned = cleaned.strip("`").strip()
    return cleaned or "(no response)"


def render_stream_text(content: str) -> Text:
    text = Text()
    for line in content.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            text.append("\n")
            continue
        if stripped.lower().startswith("title:"):
            text.append(stripped + "\n", style="bold white")
        elif stripped.lower().startswith("summary:"):
            text.append(stripped + "\n", style="bold #7dd3fc")
        elif stripped.lower().startswith("five key points:"):
            text.append(stripped + "\n", style="bold #7dd3fc")
        elif stripped.lower().startswith("notable claims"):
            text.append(stripped + "\n", style="bold #7dd3fc")
        elif stripped[:2] in {"1.", "2.", "3.", "4.", "5.", "- ", "* "}:
            text.append(stripped + "\n", style="white")
        else:
            text.append(stripped + "\n", style="white")
    return text


def _render_rich_text_block(block: str) -> Text:
    text = Text()
    for raw_line in block.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            text.append("\n")
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text.append(stripped[level:].strip() + "\n", style="bold #7dd3fc")
            continue
        if stripped[:2] in {"- ", "* "}:
            text.append(f"• {stripped[2:].strip()}\n", style="white")
            continue
        if re.match(r"^\d+\.\s", stripped):
            text.append(stripped + "\n", style="white")
            continue
        parts = re.split(r"(`[^`]+`)", line)
        for part in parts:
            if not part:
                continue
            if part.startswith("`") and part.endswith("`") and len(part) >= 2:
                text.append(part[1:-1], style="bold #7dd3fc")
            else:
                text.append(part, style="white")
        text.append("\n")
    return text


def render_message_content(content: str):
    fence_count = content.count("```")
    if fence_count % 2 == 1:
        return render_stream_text(content)

    blocks: list[object] = []
    pattern = re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", re.DOTALL)
    position = 0

    for match in pattern.finditer(content):
        before = content[position:match.start()]
        if before.strip():
            blocks.extend(_render_text_and_math(before))
        language = (match.group(1) or "text").strip() or "text"
        code = match.group(2).rstrip()
        blocks.append(
            Panel(
                Syntax(code, language, theme="monokai", word_wrap=True, line_numbers=False),
                title=f"Code · {language}",
                border_style="#334155",
                padding=(0, 1),
            )
        )
        position = match.end()

    remainder = content[position:]
    if remainder.strip():
        blocks.extend(_render_text_and_math(remainder))

    if not blocks:
        return render_stream_text(content)
    if len(blocks) == 1:
        return blocks[0]
    return Group(*blocks)


def _render_text_and_math(content: str) -> list[object]:
    segments: list[object] = []
    math_pattern = re.compile(r"(\$\$(.*?)\$\$|\\\[(.*?)\\\])", re.DOTALL)
    position = 0
    for match in math_pattern.finditer(content):
        before = content[position:match.start()]
        if before.strip():
            segments.append(_render_rich_text_block(before))
        math_body = (match.group(2) or match.group(3) or "").strip()
        if math_body:
            segments.append(
                Panel(
                    Syntax(math_body, "latex", theme="monokai", word_wrap=True, line_numbers=False),
                    title="Math",
                    border_style="#7c3aed",
                    padding=(0, 1),
                )
            )
        position = match.end()
    tail = content[position:]
    if tail.strip():
        segments.append(_render_rich_text_block(tail))
    return segments
