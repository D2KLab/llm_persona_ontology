import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # optional dependency
    load_dotenv = None

# PersonaGym/.env (repo root) and optional override from cwd
_ROOT = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(_ROOT / ".env")
    load_dotenv()


def _normalize_base_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def _strip_litellm_prefix(model: Optional[str]) -> Optional[str]:
    if not model:
        return model
    if model.startswith("openai/"):
        return model[len("openai/") :]
    return model


# Legacy provider keys (unused when LiteLLM proxy is configured)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "Insert OpenAI key here")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "Insert Claude key here")
LLAMA_API_KEY = os.getenv("LLAMA_API_KEY", "Insert Llama key here")

# Eurecom LiteLLM OpenAI-compatible proxy
LITELLM_API_BASE = _normalize_base_url(
    os.getenv("LITELLM_API_BASE", "https://litellm.tools.eurecom.fr/v1")
)
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY") or OPENAI_API_KEY
LITELLM_MODEL = _strip_litellm_prefix(
    os.getenv("LITELLM_MODEL", "Qwen/Qwen3.6-27B")
)
# Qwen3 thinking/reasoning mode (vLLM chat_template_kwargs.enable_thinking)
_LITELLM_THINKING = os.getenv("LITELLM_ENABLE_THINKING", "false").strip().lower()
LITELLM_ENABLE_THINKING = _LITELLM_THINKING in ("1", "true", "yes", "on")
USE_LITELLM = bool(LITELLM_API_BASE and LITELLM_API_KEY and "Insert" not in LITELLM_API_KEY)
