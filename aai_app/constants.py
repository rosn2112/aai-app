from pathlib import Path

APP_NAME = "AAI App"
APP_VERSION = "v0.1"
APP_TAGLINE = "Local video summaries in a terminal-native workspace"
DEFAULT_APP_HOME = Path.home() / ".aai-app"
DEFAULT_BACKEND_ORDER = ["ollama"]
DEFAULT_WHISPER_MODEL = "small.en"
DEFAULT_INFERENCE_MODE = "ollama"
DEFAULT_API_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_API_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"
DEFAULT_YOUTUBE_MODE = "auto"
DEFAULT_MLX_MODEL_REPO = "mlx-community/gemma-3-4b-it-qat-4bit"
DEFAULT_LLAMA_MODEL_REPO = "ggml-org/gemma-4-E4B-it-GGUF"
DEFAULT_LLAMA_MODEL_FILE = "gemma-4-e4b-it-Q4_K_M.gguf"
COMMANDS = [
    "/youtube",
    "/instagram",
    "/doctor",
    "/models",
    "/settings",
    "/thinking",
    "/auth",
    "/integrations",
    "/connect",
    "/tools",
    "/import",
    "/export",
    "/help",
    "/exit",
    "/yt",
    "/ig",
    "/new",
    "/sessions",
    "/resume",
]
DEFAULT_SUMMARY_PROMPT = (
    "You are summarizing a spoken video transcript. Produce plain text with:\n"
    "1. Title\n"
    "2. Five key points\n"
    "3. A concise summary paragraph\n"
    "4. Notable claims or calls to action\n"
    "Keep the summary factual, concise, and readable in a terminal."
)
DEFAULT_TRANSCRIPT_CORRECTION_PROMPT = (
    "You are correcting an automatic speech transcript from a Hindi and Sanskrit terminologies in spiritual discourses by Srila Prabhupada who is the founder of Hare Krishna movement.\n"
    "Fix obvious ASR mistakes, especially names, Hindi words, Sanskrit words, mantra fragments, and transliterated terms.\n"
    "DO NOT ADD information that was not spoken at all.\n"
    "Preserve all the proper meanings, sequences, and paragraph flow.\n"
    "Return only the corrected transcript in plain text."
)
