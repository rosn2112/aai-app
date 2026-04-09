from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aai_app.bootstrap import bootstrap
from aai_app.config import AppConfig, load_config
from aai_app.core.pipeline import summarize_url
from aai_app.doctor import get_runtime_status, run_doctor
from aai_app.parser import parse_command, parse_media_request
from aai_app.shell import run_shell
from aai_app.uninstall import launch_uninstall

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _resolve_config(app_home: str | None) -> AppConfig:
    return load_config(app_home)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    app_home: str | None = typer.Option(None, "--app-home"),
    uninstall: bool = typer.Option(False, "--uninstall", help="Remove AAI App and exit."),
) -> None:
    if uninstall:
        config = _resolve_config(app_home)
        purge_external = typer.confirm(
            "Also remove Ollama and shared model caches?",
            default=False,
        )
        path = launch_uninstall(config, purge_external=purge_external)
        typer.echo("AAI App uninstall scheduled.")
        typer.echo(f"Temporary uninstall script: {path}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        run_shell(_resolve_config(app_home))


@app.command()
def doctor(app_home: str | None = typer.Option(None, "--app-home")) -> None:
    console = Console()
    config = _resolve_config(app_home)
    runtime = get_runtime_status(config)
    table = Table(title="Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for check in run_doctor(config):
        table.add_row(check.name, "Ready" if check.ok else "Needs setup", check.detail)
    console.print(table)
    if runtime.ready:
        console.print(Panel("AAI App is ready to run local summaries.", title="Status", border_style="green"))
    else:
        detail = "\n".join(f"- {item}" for item in runtime.blocking_items)
        console.print(
            Panel(
                f"The app is not ready yet.\n\n{detail}\n\nRe-run `./install.sh` after fixing the environment.",
                title="Status",
                border_style="yellow",
            )
        )


@app.command()
def models(
    app_home: str | None = typer.Option(None, "--app-home"),
) -> None:
    console = Console()
    config = _resolve_config(app_home)
    table = Table(title="Models")
    table.add_column("Setting")
    table.add_column("Value")
    table.add_row("Inference mode", config.inference_mode)
    table.add_row("YouTube mode", config.youtube_mode)
    table.add_row("Ollama base", config.ollama_base_url)
    table.add_row("Ollama model", config.ollama_model)
    table.add_row("Whisper model", config.whisper_model_name)
    console.print(table)


@app.command()
def install_runtime(app_home: str | None = typer.Option(None, "--app-home")) -> None:
    bootstrap(app_home)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1].startswith("/"):
        console = Console()
        config = load_config()
        try:
            command = parse_command(" ".join(sys.argv[1:]))
            if command.name == "/doctor":
                doctor()
                return
            if command.name == "/models":
                models()
                return
            if not command.argument:
                raise ValueError("A URL is required for slash commands")
            media_request = parse_media_request(command.argument)
            result = summarize_url(
                command.name,
                media_request.url,
                config,
                console,
                keep_downloads=media_request.keep_downloads,
            )
            console.print(result.summary)
        except Exception as exc:
            console.print(
                Panel(
                    f"{exc}\n\nNothing ran. Use `aai-app doctor` or `/doctor` for a full readiness report.",
                    title="AAI Notice",
                    border_style="yellow",
                )
            )
        return
    app()
