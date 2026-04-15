from __future__ import annotations

import time

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.align import Align
from rich.console import Console
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.table import Table

from aai_app.config import AppConfig
from aai_app.constants import APP_NAME, APP_TAGLINE, APP_VERSION, COMMANDS
from aai_app.core.chat import chat_with_local_model, stream_chat_with_local_model
from aai_app.core.pipeline import summarize_url
from aai_app.doctor import get_runtime_status, run_doctor
from aai_app.integrations import (
    enable_integration,
    export_to_mcp,
    list_mcp_tools,
    load_integration_configs,
    import_from_mcp,
)
from aai_app.memory import ChatSession, MemoryStore
from aai_app.parser import parse_command, parse_media_request
from aai_app.rendering import render_message_content, render_stream_text


PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "bold #f5f7fa",
        "app": "bold #7dd3fc",
        "arrow": "bold #60a5fa",
        "toolbar": "bg:#0f172a #cbd5e1",
    }
)


def _help_panel() -> Panel:
    command_table = Table(box=None, show_header=True, header_style="bold #7dd3fc", pad_edge=False)
    command_table.add_column("Command", style="bold white", no_wrap=True)
    command_table.add_column("Purpose", style="#94a3b8")
    command_table.add_row("plain text", "Chat with the selected assistant backend")
    command_table.add_row("/youtube <url> [--keep-downloads]", "Summarize a YouTube video")
    command_table.add_row("/instagram <url> [--keep-downloads]", "Summarize an Instagram reel")
    command_table.add_row("/doctor", "Show install status and missing requirements")
    command_table.add_row("/models", "Show the current backend and installed model paths")
    command_table.add_row("/settings", "Show runtime settings and local model configuration")
    command_table.add_row("/thinking [on|off]", "Toggle the thinking/status metadata block")
    command_table.add_row("/auth", "Configure Ollama and optional Gemini YouTube settings")
    command_table.add_row("/integrations", "List configured MCP integrations")
    command_table.add_row("/connect <server>", "Enable an MCP integration profile and show setup guidance")
    command_table.add_row("/tools <server>", "List tools exposed by a configured MCP integration")
    command_table.add_row("/import <server> <query>", "Pull context from an MCP integration")
    command_table.add_row("/export <server> [title]", "Export the current chat to an MCP integration")
    command_table.add_row("/new", "Start a fresh saved chat session")
    command_table.add_row("/sessions", "List recent chats with simple numbers")
    command_table.add_row("/resume [n]", "Resume the latest chat or session number")
    command_table.add_row("/help", "Show command guide")
    command_table.add_row("/exit", "Leave the app")
    return Panel(
        command_table,
        title="Command Palette",
        subtitle="Slash commands",
        border_style="#334155",
        padding=(1, 2),
    )


def _doctor_table(config: AppConfig) -> Table:
    table = Table(title="System Doctor", header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("Check", style="bold white", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="#94a3b8")
    for check in run_doctor(config):
        status = "[green]ready[/green]" if check.ok else "[yellow]setup needed[/yellow]"
        table.add_row(check.name, status, check.detail)
    return table


def _models_table(config: AppConfig) -> Table:
    table = Table(title="Model Configuration", header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("Setting", style="bold white", no_wrap=True)
    table.add_column("Value", style="#94a3b8")
    table.add_row("Inference mode", config.inference_mode)
    table.add_row("YouTube processing", config.youtube_mode)
    table.add_row("Ollama endpoint", config.ollama_base_url)
    table.add_row("Ollama model", config.ollama_model)
    table.add_row("Whisper model", config.whisper_model_name)
    table.add_row("yt-dlp binary", config.yt_dlp_path or "not configured")
    table.add_row("ffmpeg binary", config.ffmpeg_path or "not configured")
    return table


def _settings_table(config: AppConfig) -> Table:
    table = Table(title="Application Settings", header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("Setting", style="bold white", no_wrap=True)
    table.add_column("Value", style="#94a3b8")
    table.add_row("Inference mode", config.inference_mode)
    table.add_row("YouTube processing", config.youtube_mode)
    table.add_row("Ollama endpoint", config.ollama_base_url)
    table.add_row("Ollama model", config.ollama_model)
    table.add_row("Gemini key", "configured" if config.google_api_key.strip() else "missing")
    table.add_row("Saved downloads folder", config.downloads_dir)
    table.add_row("Thinking block", "shown" if config.show_thinking else "hidden")
    return table


def _integrations_table(config: AppConfig) -> Table:
    table = Table(title="MCP Integrations", header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("Name", style="bold white", no_wrap=True)
    table.add_column("Status", style="#94a3b8", no_wrap=True)
    table.add_column("Command", style="#94a3b8")
    table.add_column("Notes", style="white")
    for server in load_integration_configs(config):
        status = "enabled" if server.enabled else "disabled"
        command = " ".join([server.command, *server.args]).strip()
        notes = server.description or ""
        if server.setup_url:
            notes = f"{notes}\nsetup: {server.setup_url}".strip()
        table.add_row(server.name, status, command or "-", notes)
    return table


def _session_table(memory: MemoryStore, current_session: ChatSession) -> Table:
    table = Table(title="Saved Sessions", header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("#", style="bold white", no_wrap=True, justify="right")
    table.add_column("Status", style="#94a3b8", no_wrap=True)
    table.add_column("Updated", style="#94a3b8")
    table.add_column("Title", style="white")
    sessions = memory.list_sessions()
    if not sessions:
        table.add_row("-", "-", "-", "No saved sessions yet")
        return table
    for index, session in enumerate(sessions[:10], start=1):
        status = "active" if session.session_id == current_session.session_id else ""
        table.add_row(str(index), status, session.updated_at[:19].replace("T", " "), session.title)
    return table


def _centered(renderable: object, width: int = 96) -> Align:
    return Align.center(renderable, vertical="middle", width=width)


def _startup_view(config: AppConfig, session: ChatSession) -> Group:
    runtime = get_runtime_status(config)
    accent = "#22c55e" if runtime.ready else "#f59e0b"

    overview = Panel(
        Align.center(
            Text.assemble(
                ("AAI APP\n", "bold white"),
                (f"{APP_VERSION}\n", "#94a3b8"),
                (f"{APP_TAGLINE}\n\n", "#7dd3fc"),
                ("Interactive shell for local video understanding.\n", "#94a3b8"),
                ("No web API keys. No browser UI. Terminal-first workflow.\n\n", "#94a3b8"),
                ("Current chat\n", "bold white"),
                (f"{session.title}\n", "white"),
                (f"{len(session.messages)} saved messages\n\n", "#94a3b8"),
                ("Examples\n", "bold white"),
                ("  /youtube https://youtu.be/...\n", "white"),
                ("  /instagram https://www.instagram.com/reel/...\n", "white"),
                ("  Ask a question directly to chat locally\n", "white"),
            ),
        ),
        title="Workspace",
        subtitle="Local-first terminal",
        border_style="#334155",
        padding=(1, 3),
        width=96,
    )

    if runtime.ready:
        readiness_body = Text.assemble(
            ("System ready\n", "bold #22c55e"),
            ("Models and local binaries appear available.\n", "#94a3b8"),
            ("\nUse /doctor for the detailed report.", "white"),
        )
    else:
        readiness_body = Text.assemble(
            ("Setup still needed\n", "bold #f59e0b"),
            *[(f"- {item}\n", "white") for item in runtime.blocking_items],
            ("\nRun /doctor for details. Re-run ./install.sh if required.", "#94a3b8"),
        )

    readiness = Panel(
        Align.center(readiness_body),
        title="Readiness",
        border_style=accent,
        padding=(1, 3),
        width=96,
    )

    return Group(_centered(overview), _centered(readiness))


def _summary_panel(summary: str, backend: str, platform_name: str) -> Panel:
    body = Text()
    body.append(f"backend  {backend}\n", style="bold #7dd3fc")
    body.append(f"source   {platform_name}\n\n", style="#94a3b8")
    body.append(summary.strip(), style="white")
    return Panel(body, title="Summary", subtitle="Local output", border_style="#22c55e", padding=(1, 3), width=96)


def _summary_result_panel(summary: str, backend: str, platform_name: str, artifact_dir: str | None) -> Panel:
    body = Text()
    body.append(f"backend  {backend}\n", style="bold #7dd3fc")
    body.append(f"source   {platform_name}\n", style="#94a3b8")
    if artifact_dir:
        body.append(f"saved    {artifact_dir}\n", style="#94a3b8")
    body.append("\n")
    body.append(summary.strip(), style="white")
    return Panel(body, title="Summary", subtitle="Output", border_style="#22c55e", padding=(1, 3), width=96)


def _transcript_panel(title: str, content: str, border_style: str) -> Panel:
    return Panel(
        render_message_content(content.strip() if content.strip() else "(empty)"),
        title=title,
        border_style=border_style,
        padding=(1, 3),
        width=96,
    )


def _summary_output_group(
    summary: str,
    transcript: str,
    corrected_transcript: str,
    backend: str,
    platform_name: str,
    artifact_dir: str | None,
) -> Group:
    renderables: list[object] = [
        _summary_result_panel(summary, backend, platform_name, artifact_dir),
    ]
    if corrected_transcript.strip():
        renderables.append(_transcript_panel("Corrected Transcript", corrected_transcript, "#38bdf8"))
    if transcript.strip():
        renderables.append(_transcript_panel("Raw Transcript", transcript, "#475569"))
    return Group(*renderables)


def _chat_panel(
    reply: str,
    backend: str,
    session: ChatSession,
    show_thinking: bool = False,
    elapsed_seconds: float = 0.0,
    thinking: str = "",
) -> Panel:
    body = Text()
    if show_thinking:
        approx_tokens = max(1, len(reply) // 4) if reply.strip() else 0
        tokens_per_second = (approx_tokens / elapsed_seconds) if elapsed_seconds > 0 and approx_tokens > 0 else 0.0
        body.append(f"Model: {backend}\n", style="bold #7dd3fc")
        body.append(f"Elapsed: {elapsed_seconds:.1f}s\n", style="#94a3b8")
        if approx_tokens > 0:
            body.append(f"Approx speed: {tokens_per_second:.1f} tok/s\n", style="#94a3b8")
        body.append("\n")
        renderables: list[object] = [body]
        if thinking.strip():
            thinking_text = Text()
            thinking_text.append("Thinking\n", style="bold #a78bfa")
            thinking_text.append(thinking.strip(), style="#c4b5fd")
            renderables.append(Panel(thinking_text, border_style="#7c3aed", padding=(0, 1)))
        if reply.strip():
            renderables.append(render_message_content(reply))
        else:
            renderables.append(render_message_content("(no response)"))
        content_renderable = Group(*renderables)
    else:
        content_renderable = render_message_content(reply)
    subtitle = "Thinking" if show_thinking else None
    return Panel(content_renderable, subtitle=subtitle, border_style="#38bdf8", padding=(1, 3), width=96)


def _stream_panel(content: str, backend: str, phase: str, show_thinking: bool, elapsed_seconds: float, thinking: str = "") -> Panel:
    body = Text()
    if show_thinking:
        approx_tokens = max(1, len(content) // 4) if content.strip() else 0
        tokens_per_second = (approx_tokens / elapsed_seconds) if elapsed_seconds > 0 and approx_tokens > 0 else 0.0
        body.append(f"Model: {backend}\n", style="bold #7dd3fc")
        body.append(f"Status: {phase}\n", style="#94a3b8")
        body.append(f"Elapsed: {elapsed_seconds:.1f}s\n", style="#94a3b8")
        if approx_tokens > 0:
            body.append(f"Approx speed: {tokens_per_second:.1f} tok/s\n", style="#94a3b8")
        body.append("\n")
    renderables: list[object] = [body]
    if show_thinking and thinking.strip():
        thinking_text = Text()
        thinking_text.append("Thinking\n", style="bold #a78bfa")
        thinking_text.append(thinking.strip(), style="#c4b5fd")
        renderables.append(Panel(thinking_text, border_style="#7c3aed", padding=(0, 1)))
    renderables.append(render_stream_text(content if content.strip() else "Generating..."))
    subtitle = "Thinking" if show_thinking else None
    return Panel(Group(*renderables), subtitle=subtitle, border_style="#38bdf8", padding=(1, 3), width=96)


def _thinking_panel(config: AppConfig) -> Panel:
    state = "enabled" if config.show_thinking else "disabled"
    body = Text()
    body.append(f"Thinking block {state}.\n\n", style="bold #22c55e")
    body.append("Use `/thinking on` or `/thinking off` to change it.", style="#94a3b8")
    return Panel(body, title="Display", border_style="#22c55e", padding=(1, 3), width=96)


def _friendly_error(exc: Exception) -> Panel:
    return Panel(
        Text.assemble(
            ("Nothing ran\n", "bold #f59e0b"),
            (f"{exc}\n", "white"),
            ("\nUse /doctor to inspect the environment.", "#94a3b8"),
        ),
        title="AAI Notice",
        border_style="#f59e0b",
        padding=(1, 3),
        width=96,
    )


def _integration_panel(title: str, body_text: str) -> Panel:
    return Panel(
        body_text.strip(),
        title=title,
        border_style="#38bdf8",
        padding=(1, 3),
        width=96,
    )


def _connect_panel(server_name: str, enabled: bool, auth_hint: str, setup_url: str) -> Panel:
    body = Text()
    body.append(f"Integration profile: {server_name}\n", style="bold #22c55e")
    body.append(f"status               {'enabled' if enabled else 'disabled'}\n", style="#94a3b8")
    if auth_hint:
        body.append(f"\nAuth/setup\n{auth_hint}\n", style="white")
    if setup_url:
        body.append(f"\nReference\n{setup_url}\n", style="#7dd3fc")
    return Panel(body, title="Integration", border_style="#22c55e", padding=(1, 3), width=96)


def _auth_panel(config: AppConfig) -> Panel:
    body = Text()
    body.append("Provider settings saved.\n\n", style="bold #22c55e")
    body.append(f"Inference mode        {config.inference_mode}\n", style="#94a3b8")
    body.append(f"YouTube processing    {config.youtube_mode}\n", style="#94a3b8")
    body.append(f"Ollama model          {config.ollama_model}\n", style="#94a3b8")
    body.append(f"Gemini key            {'configured' if config.google_api_key.strip() else 'missing'}\n", style="#94a3b8")
    return Panel(body, title="Provider Setup", border_style="#22c55e", padding=(1, 3), width=96)


def _prompt_message() -> list[tuple[str, str]]:
    return [
        ("class:app", "aai-app"),
        ("class:arrow", "  "),
        ("class:prompt", "› "),
    ]


def _toolbar_text() -> str:
    return " enter submit  tab complete  up/down history  plain text = chat  /auth provider setup  /doctor install status "


def _preferred_backend_label(config: AppConfig) -> str:
    return "ollama"


def _prompt_for_choice(session: PromptSession, title: str, options: list[tuple[str, str, str]], default_value: str) -> str:
    console = Console()
    table = Table(title=title, header_style="bold #7dd3fc", border_style="#334155")
    table.add_column("#", style="bold white", no_wrap=True, justify="right")
    table.add_column("Choice", style="bold white", no_wrap=True)
    table.add_column("Meaning", style="#94a3b8")
    default_index = 1
    for index, (value, label, description) in enumerate(options, start=1):
        if value == default_value:
            default_index = index
        table.add_row(str(index), label, description)
    console.print(_centered(table, width=108))
    raw = session.prompt(f"Choose 1-{len(options)} [{default_index}]: ").strip()
    if not raw:
        return options[default_index - 1][0]
    if raw.isdigit():
        selected = int(raw)
        if 1 <= selected <= len(options):
            return options[selected - 1][0]
    raise ValueError(f"Choose a number between 1 and {len(options)}.")

def _run_auth_flow(session: PromptSession, config: AppConfig) -> AppConfig:
    console = Console()
    youtube_mode = _prompt_for_choice(
        session,
        "YouTube Processing Mode",
        [
            ("auto", "Automatic", "Use Gemini direct mode when available, otherwise transcript mode."),
            ("gemini", "Gemini direct", "Ask Gemini to summarize the YouTube URL directly."),
            ("transcript", "Transcript only", "Always download audio, transcribe, and summarize."),
        ],
        config.youtube_mode,
    )

    ollama_base_url = session.prompt(
        "Ollama base URL: ",
        default=config.ollama_base_url,
    ).strip() or config.ollama_base_url
    ollama_model = session.prompt(
        "Ollama model name: ",
        default=config.ollama_model,
    ).strip() or config.ollama_model

    google_api_key = session.prompt(
        "Gemini API key for YouTube direct mode (Enter keeps current, '-' clears it): ",
        is_password=True,
    ).strip()

    config.inference_mode = "ollama"
    config.youtube_mode = youtube_mode
    config.ollama_base_url = ollama_base_url
    config.ollama_model = ollama_model
    if google_api_key == "-":
        config.google_api_key = ""
    elif google_api_key:
        config.google_api_key = google_api_key
    config.save()
    console.print(_centered(_auth_panel(config), width=96))
    return config


def run_shell(config: AppConfig) -> None:
    console = Console()
    memory = MemoryStore(config)
    current_session = memory.get_active_session()
    history = FileHistory(str(config.logs_dir / "history.txt"))
    session = PromptSession(
        message=_prompt_message,
        history=history,
        style=PROMPT_STYLE,
        auto_suggest=AutoSuggestFromHistory(),
        completer=WordCompleter(COMMANDS, ignore_case=True),
        complete_while_typing=True,
        bottom_toolbar=_toolbar_text,
    )

    console.print(_startup_view(config, current_session))
    console.print(_centered(Rule(style="#1e293b"), width=96))
    console.print(_centered(Panel("Type `/help` for commands.", border_style="#334155", padding=(0, 2), width=96), width=96))

    while True:
        try:
            raw = session.prompt()
        except (KeyboardInterrupt, EOFError):
            console.print("\nExiting AAI App.")
            return

        try:
            if raw.strip().startswith("/"):
                command = parse_command(raw)
                if command.name in {"/exit", "/quit"}:
                    console.print("Exiting AAI App.")
                    return
                if command.name == "/help":
                    console.print(_centered(_help_panel(), width=96))
                    continue
                if command.name == "/doctor":
                    console.print(_centered(_doctor_table(config), width=96))
                    continue
                if command.name == "/models":
                    model_scope = (command.argument or "").strip().lower()
                    console.print(_centered(_models_table(config), width=96))
                    continue
                if command.name == "/settings":
                    console.print(_centered(_settings_table(config), width=96))
                    continue
                if command.name == "/thinking":
                    choice = (command.argument or "").strip().lower()
                    if choice in {"on", "true", "show"}:
                        config.show_thinking = True
                    elif choice in {"off", "false", "hide"}:
                        config.show_thinking = False
                    elif choice == "":
                        config.show_thinking = not config.show_thinking
                    else:
                        raise ValueError("Use /thinking, /thinking on, or /thinking off")
                    config.save()
                    console.print(_centered(_thinking_panel(config), width=96))
                    continue
                if command.name == "/auth":
                    config = _run_auth_flow(session, config)
                    continue
                if command.name == "/integrations":
                    console.print(_centered(_integrations_table(config), width=96))
                    continue
                if command.name == "/connect":
                    target = (command.argument or "").strip()
                    if not target:
                        raise ValueError("Use /connect <server>")
                    server = enable_integration(config, target)
                    console.print(
                        _centered(
                            _connect_panel(server.name, server.enabled, server.auth_hint, server.setup_url),
                            width=96,
                        )
                    )
                    continue
                if command.name == "/tools":
                    target = (command.argument or "").strip()
                    if not target:
                        raise ValueError("Use /tools <server>")
                    tools = list_mcp_tools(config, target)
                    if not tools:
                        raise RuntimeError(f"No tools were exposed by '{target}'.")
                    console.print(
                        _centered(
                            _integration_panel("MCP Tools", f"server  {target}\n\n" + "\n".join(f"- {tool}" for tool in tools)),
                            width=96,
                        )
                    )
                    continue
                if command.name == "/new":
                    current_session = memory.create_session()
                    console.print(
                        _centered(Panel(
                            f"Started a new chat session.\n\nchat  {current_session.title}",
                            title="Session",
                            border_style="#38bdf8",
                            padding=(1, 3),
                            width=96,
                        ), width=96)
                    )
                    continue
                if command.name == "/sessions":
                    console.print(_centered(_session_table(memory, current_session), width=96))
                    continue
                if command.name == "/resume":
                    current_session = memory.resolve_session_reference(command.argument)
                    console.print(
                        _centered(Panel(
                            f"Resumed chat.\n\n{current_session.title}",
                            title="Session",
                            border_style="#38bdf8",
                            padding=(1, 3),
                            width=96,
                        ), width=96)
                    )
                    continue
                if command.name == "/import":
                    if not command.argument:
                        raise ValueError("Use /import <server> <query>")
                    server_name, _, query = command.argument.partition(" ")
                    if not query.strip():
                        raise ValueError("Use /import <server> <query>")
                    imported = import_from_mcp(config, server_name, query.strip())
                    current_session = memory.append_message(
                        current_session,
                        "system",
                        f"Imported context from {server_name}:\n\n{imported}",
                    )
                    console.print(
                        _centered(
                            _integration_panel(
                                "Imported Context",
                                f"source  {server_name}\n\n{imported}",
                            ),
                            width=96,
                        )
                    )
                    continue
                if command.name == "/export":
                    if not command.argument:
                        raise ValueError("Use /export <server> [title]")
                    server_name, _, title = command.argument.partition(" ")
                    export_title = title.strip() or current_session.title
                    transcript = memory.render_session_transcript(current_session)
                    if not transcript:
                        raise ValueError("The current chat is empty, so there is nothing to export.")
                    exported = export_to_mcp(config, server_name, export_title, transcript)
                    console.print(
                        _centered(
                            _integration_panel(
                                "Export Complete",
                                f"target  {server_name}\n"
                                f"title   {export_title}\n\n"
                                f"{exported or 'The MCP server accepted the export request.'}",
                            ),
                            width=96,
                        )
                    )
                    continue
                if command.name not in {"/youtube", "/instagram", "/yt", "/ig"}:
                    raise ValueError(f"Unknown command: {command.name}")
                if not command.argument:
                    raise ValueError("A URL is required for this command")
                media_request = parse_media_request(command.argument)
                result = summarize_url(
                    command.name,
                    media_request.url,
                    config,
                    console,
                    keep_downloads=media_request.keep_downloads,
                )
                console.print(
                    _centered(
                        _summary_output_group(
                            result.summary,
                            result.transcript,
                            result.corrected_transcript,
                            result.backend,
                            result.platform,
                            result.artifact_dir,
                        ),
                        width=96,
                    )
                )
                continue

            memory.append_message(current_session, "user", raw.strip())
            conversation = [
                {"role": message.role, "content": message.content}
                for message in current_session.messages
                if message.role in {"user", "assistant"}
            ]
            backend = _preferred_backend_label(config)
            reply = ""
            thinking = ""
            started_at = time.perf_counter()
            with Live(
                _centered(_stream_panel("", backend, "Generating locally", config.show_thinking, 0.0, ""), width=96),
                console=console,
                refresh_per_second=8,
                transient=False,
            ) as live:
                for backend, partial, thinking_partial in stream_chat_with_local_model(raw.strip(), conversation[:-1], config):
                    reply = partial
                    thinking = thinking_partial
                    elapsed = time.perf_counter() - started_at
                    live.update(_centered(_stream_panel(reply, backend, "Generating locally", config.show_thinking, elapsed, thinking), width=96))
                elapsed = time.perf_counter() - started_at
                live.update(_centered(_chat_panel(reply, backend, current_session, config.show_thinking, elapsed, thinking), width=96))
            current_session = memory.append_message(current_session, "assistant", reply)
        except Exception as exc:
            console.print(_centered(_friendly_error(exc), width=96))
