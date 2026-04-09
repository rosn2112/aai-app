#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${AAI_APP_HOME:-$HOME/.aai-app}"
VENV_DIR="$APP_HOME/venv"
LOCAL_BIN="$HOME/.local/bin"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INFERENCE_MODE="${AAI_INFERENCE_MODE:-}"
GOOGLE_API_KEY_VALUE="${AAI_GOOGLE_API_KEY:-}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "AAI App v0.1 currently supports macOS only."
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required but was not found."
  exit 1
fi

mkdir -p "$APP_HOME" "$LOCAL_BIN"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

ensure_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required for the CLI-only Ollama install, but it was not found."
    echo "Install Homebrew first, then rerun ./install.sh."
    exit 1
  fi

  echo "Ollama CLI is not installed. Installing the Homebrew formula..."
  HOMEBREW_NO_AUTO_UPDATE=1 NONINTERACTIVE=1 brew install ollama

  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama installation completed, but the 'ollama' command is still not available on PATH."
    echo "Open a new terminal and rerun ./install.sh."
    exit 1
  fi
}

wait_for_ollama() {
  local attempt
  if command -v ollama >/dev/null 2>&1 && ollama list >/dev/null 2>&1; then
    return 0
  fi

  nohup ollama serve >/dev/null 2>&1 &

  for attempt in {1..30}; do
    if ollama list >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Ollama did not become ready in time."
  echo "Try running 'ollama list' manually after installation."
  exit 1
}

INFERENCE_MODE="${INFERENCE_MODE:-ollama}"

cat <<'EOF'

AAI App installs with an Ollama-only local runtime.
Default Ollama model:
  - gemma4:e4b

The installer will:
  - set up the Python environment
  - install Whisper dependencies
  - pull the default Ollama model
  - install the aai-app launcher

EOF

ensure_ollama
wait_for_ollama

if [[ -z "$GOOGLE_API_KEY_VALUE" && -t 0 ]]; then
  printf "Optional Google API key for direct YouTube summarization (leave blank to skip): "
  read -rs GOOGLE_API_KEY_VALUE
  printf '\n'
fi

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$ROOT_DIR[runtime,mcp]"
BOOTSTRAP_ARGS=(--app-home "$APP_HOME" --inference-mode "$INFERENCE_MODE")
if [[ -n "$GOOGLE_API_KEY_VALUE" ]]; then
  BOOTSTRAP_ARGS+=(--google-api-key "$GOOGLE_API_KEY_VALUE")
fi
python -m aai_app.bootstrap "${BOOTSTRAP_ARGS[@]}"

ln -sf "$VENV_DIR/bin/aai-app" "$LOCAL_BIN/aai-app"

if ! grep -qs '# >>> AAI App PATH >>>' "$HOME/.zshrc" 2>/dev/null; then
  cat >> "$HOME/.zshrc" <<'EOF'

# >>> AAI App PATH >>>
export PATH="$HOME/.local/bin:$PATH"
# <<< AAI App PATH <<<
EOF
fi

cat <<EOF

Installation complete.

Local install notes:
  - Local backend: Ollama
  - Default Ollama model: gemma4:e4b

Run:
  source "$HOME/.zshrc"
  # or open a new terminal window
  aai-app

If you skipped credentials during install, open the app and run:
  /auth

Uninstall later with:
  aai-app --uninstall

EOF
