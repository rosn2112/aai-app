from __future__ import annotations

from dataclasses import dataclass
import shlex


@dataclass
class ParsedCommand:
    name: str
    argument: str | None = None


@dataclass
class MediaRequest:
    url: str
    keep_downloads: bool = False


def parse_command(raw: str) -> ParsedCommand:
    text = raw.strip()
    if not text:
        raise ValueError("Enter a command. Type /help for available commands.")
    if not text.startswith("/"):
        raise ValueError("Commands must start with '/'. Type /help for available commands.")

    parts = text.split(maxsplit=1)
    name = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else None
    return ParsedCommand(name=name, argument=argument)


def parse_media_request(argument: str) -> MediaRequest:
    tokens = shlex.split(argument)
    keep_downloads = False
    url = ""
    for token in tokens:
        if token == "--keep-downloads":
            keep_downloads = True
            continue
        if not url:
            url = token
            continue
        raise ValueError("Only one URL is supported. Usage: /youtube <url> [--keep-downloads]")
    if not url:
        raise ValueError("A URL is required.")
    return MediaRequest(url=url, keep_downloads=keep_downloads)
