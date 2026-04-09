# AAI App Local Terminal Edition

## Install

```bash
./install.sh
```

The installer creates `~/.aai-app`, installs the Python runtime, downloads local models, installs a launcher command, and prints the next steps when it completes.
During install, the user can choose:
- `local` mode: downloads local LLM weights and uses local RAM
- `api` mode: skips local LLM weights and uses an API key
- `auto` mode: prefers local models and can fall back to API

Default local fallback model:
- `llama.cpp` with `Gemma 4 E4B Instruct Q4_K_M GGUF`

After install, refresh your shell:

```bash
source ~/.zshrc
```

or open a new terminal window, then run:

```bash
aai-app
```

It also prepares an MCP integration registry at:

```bash
~/.aai-app/mcp_servers.json
```

The default file includes a disabled Notion example profile that can be enabled and configured for import/export workflows.

## Lightweight UI Test

If you only want to test the shell and terminal UI without downloading models:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
aai-app
```

This path supports:
- plain text chat with the local shell interface
- `/help`
- `/doctor`
- `/models`
- `/settings`
- `/auth`
- `/integrations`
- `/import <server> <query>`
- `/export <server> [title]`
- `/new`
- `/sessions`
- `/resume [n]`
- `/exit`

The media summary commands will stop gracefully until the runtime dependencies and models are installed.

## Run

```bash
aai-app
```

## Commands

```text
plain text chat
/youtube <url> [--keep-downloads]
/instagram <url> [--keep-downloads]
/doctor
/models
/settings
/auth
/integrations
/import <server> <query>
/export <server> [title]
/new
/sessions
/resume [n]
/help
/exit
```

`--keep-downloads` stores downloaded artifacts in `~/Downloads/aai-app/downloadedContent/...`. Without the flag, the app uses a temporary path and removes the artifacts after processing.

If you skip API credentials during install, run `/auth` inside the app later to configure:
- inference mode
- API key
- API base URL
- API model
- Google API key for YouTube fast-path summarization

## Uninstall

You can remove the app with:

```bash
aai-app --uninstall
```

The uninstall flow can optionally remove:
- `~/.ollama`
- `~/.cache/huggingface`
- `~/.cache/mlx`
- `~/.cache/llama.cpp`

Choose that option only if you want to remove shared global model caches, not just AAI App files.

You can also run one-shot commands:

```bash
aai-app /youtube <url>
aai-app /instagram <url>
```
