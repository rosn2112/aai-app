# AAI App v0.1

Terminal-first video summarizer for macOS.

## Included
- Ollama CLI setup through Homebrew
- Automatic `gemma4:e4b` model bootstrap
- Whisper runtime bootstrap
- `aai-app` terminal launcher

## Install
```bash
git clone https://github.com/rosn2112/aai-app
cd aai-app-v0.1
./install.sh
source ~/.zshrc
```

## Run
```bash
aai-app
```

## Commands
- plain text: local chat with Gemma 4 through Ollama
- `/youtube <url>`
- `/instagram <url>`
- `/doctor`
- `/settings`
- `/auth`

## Notes
- macOS only
- Homebrew is required
- If `gemma4:e4b` is already installed in Ollama, the installer will reuse it
- If the model pull fails during install, run:
```bash
ollama pull gemma4:e4b
./install.sh
```

## Uninstall
```bash
aai-app --uninstall
```


## Upgrade
```bash
aai-app --upgrade
```

## MCP Integrations
- `/integrations` lists configured MCP profiles
- `/connect <server>` enables a profile and shows setup guidance
- `/tools <server>` lists MCP tools for a configured stdio server
- `/import <server> <query>` and `/export <server> [title]` use the selected MCP server
