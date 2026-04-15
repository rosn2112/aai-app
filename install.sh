#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${AAI_APP_HOME:-$HOME/.aai-app}"
VENV_DIR="$APP_HOME/venv"
LOCAL_BIN="$HOME/.local/bin"
PYTHON_BIN="${PYTHON_BIN:-}"
INFERENCE_MODE="${AAI_INFERENCE_MODE:-}"
GOOGLE_API_KEY_VALUE="${AAI_GOOGLE_API_KEY:-}"

python_meets_requirement() {
  local candidate="$1"
  "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

python_major_minor() {
  local candidate="$1"
  "$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
}

select_python() {
  local candidates=()
  local candidate

  if [[ -n "$PYTHON_BIN" ]]; then
    candidates+=("$PYTHON_BIN")
  fi

  candidates+=(
    /opt/homebrew/bin/python3
    /usr/local/bin/python3
    python3.14
    python3.13
    python3.12
    python3.11
    python3.10
    python3
  )

  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 && python_meets_requirement "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done

  return 1
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "AAI App v0.1 currently supports macOS only."
  exit 1
fi

if ! PYTHON_BIN="$(select_python)"; then
  echo "Python 3.10 or newer is required but was not found."
  echo "Install a newer Python (Homebrew Python is preferred), then rerun ./install.sh."
  exit 1
fi

mkdir -p "$APP_HOME" "$LOCAL_BIN"

SELECTED_PYTHON_MM="$(python_major_minor "$PYTHON_BIN")"

if [[ -d "$VENV_DIR" ]]; then
  if [[ ! -x "$VENV_DIR/bin/python" ]] || ! python_meets_requirement "$VENV_DIR/bin/python"; then
    rm -rf "$VENV_DIR"
  elif [[ "$(python_major_minor "$VENV_DIR/bin/python")" != "$SELECTED_PYTHON_MM" ]]; then
    rm -rf "$VENV_DIR"
  fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_APP="$VENV_DIR/bin/aai-app"

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

"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install -e "$ROOT_DIR[runtime,mcp]"
BOOTSTRAP_ARGS=(--app-home "$APP_HOME" --inference-mode "$INFERENCE_MODE")
if [[ -n "$GOOGLE_API_KEY_VALUE" ]]; then
  BOOTSTRAP_ARGS+=(--google-api-key "$GOOGLE_API_KEY_VALUE")
fi
"$VENV_PYTHON" -m aai_app.bootstrap "${BOOTSTRAP_ARGS[@]}"

ln -sf "$VENV_APP" "$LOCAL_BIN/aai-app"

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
