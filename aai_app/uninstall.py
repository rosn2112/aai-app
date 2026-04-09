from __future__ import annotations

import argparse
import stat
import subprocess
import tempfile
from pathlib import Path

from aai_app.config import AppConfig, load_config

PATH_BLOCK_BEGIN = "# >>> AAI App PATH >>>"
PATH_BLOCK_END = "# <<< AAI App PATH <<<"

def _build_uninstall_script(config: AppConfig, purge_external: bool) -> str:
    app_home = config.home_path
    launcher_path = Path.home() / ".local" / "bin" / "aai-app"
    zshrc = Path.home() / ".zshrc"
    external_cleanup = ""
    if purge_external:
        external_cleanup = """
rm -rf "$HOME/.ollama"
rm -rf "$HOME/.cache/huggingface"
rm -rf "$HOME/.cache/mlx"
rm -rf "$HOME/.cache/llama.cpp"
"""
    return f"""#!/usr/bin/env bash
set -euo pipefail

WAIT_PID="${{1:-}}"
APP_HOME="{app_home}"
LAUNCHER_PATH="{launcher_path}"
ZSHRC_PATH="{zshrc}"
PATH_BLOCK_BEGIN="{PATH_BLOCK_BEGIN}"
PATH_BLOCK_END="{PATH_BLOCK_END}"
SELF_PATH="${{BASH_SOURCE[0]}}"
SELF_DIR="$(cd "$(dirname "$SELF_PATH")" && pwd)"

if [[ -n "$WAIT_PID" ]]; then
  while kill -0 "$WAIT_PID" >/dev/null 2>&1; do
    sleep 1
  done
fi

terminate_matching_processes() {{
  local pids
  pids="$(pgrep -f "$APP_HOME" || true)"
  if [[ -n "$pids" ]]; then
    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      if [[ "$pid" != "$$" ]]; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done <<< "$pids"
    sleep 1
    pids="$(pgrep -f "$APP_HOME" || true)"
    if [[ -n "$pids" ]]; then
      while IFS= read -r pid; do
        [[ -z "$pid" ]] && continue
        if [[ "$pid" != "$$" ]]; then
          kill -9 "$pid" >/dev/null 2>&1 || true
        fi
      done <<< "$pids"
    fi
  fi
}}

cleanup_self() {{
  rm -f "$SELF_PATH" >/dev/null 2>&1 || true
  rmdir "$SELF_DIR" >/dev/null 2>&1 || true
}}

trap cleanup_self EXIT

terminate_matching_processes

if [[ -f "$ZSHRC_PATH" ]]; then
  TMP_FILE="$(mktemp)"
  awk -v begin="$PATH_BLOCK_BEGIN" -v end="$PATH_BLOCK_END" '
    $0 == begin {{ skip=1; next }}
    $0 == end   {{ skip=0; next }}
    !skip {{ print }}
  ' "$ZSHRC_PATH" > "$TMP_FILE"
  mv "$TMP_FILE" "$ZSHRC_PATH"
  python3 - <<'PY'
from pathlib import Path
path = Path("{zshrc}")
if path.exists():
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip() != 'export PATH="$HOME/.local/bin:$PATH"']
    path.write_text("\\n".join(lines).rstrip() + "\\n", encoding="utf-8")
PY
fi

rm -f "$LAUNCHER_PATH"
rm -rf "$APP_HOME"
{external_cleanup}

echo "AAI App has been removed."
echo "Open a new terminal window or run: source ~/.zshrc"
"""


def write_uninstall_script(config: AppConfig, purge_external: bool = False) -> Path:
    script_dir = Path(tempfile.mkdtemp(prefix="aai-uninstall-"))
    script_path = script_dir / "uninstall.sh"
    script_path.write_text(
        _build_uninstall_script(config, purge_external=purge_external),
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    return script_path


def launch_uninstall(
    config: AppConfig,
    wait_pid: int | None = None,
    purge_external: bool = False,
) -> Path:
    script_path = write_uninstall_script(config, purge_external=purge_external)
    args = [str(script_path)]
    if wait_pid is not None:
        args.append(str(wait_pid))
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return script_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-home", default=None)
    parser.add_argument("--write-script-only", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--wait-pid", type=int, default=None)
    parser.add_argument("--purge-external", action="store_true")
    args = parser.parse_args()

    config = load_config(args.app_home)
    if args.launch:
        launch_uninstall(config, wait_pid=args.wait_pid, purge_external=args.purge_external)
        return
    path = write_uninstall_script(config, purge_external=args.purge_external)
    print(path)


if __name__ == "__main__":
    main()
