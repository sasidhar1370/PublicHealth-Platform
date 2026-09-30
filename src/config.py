"""Configuration module for the Study Assistant application.

Centralizes paths, multi-provider configurations, model identifiers, chunking parameters,
and safe multi-key retrieval and rotation.
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Suppress OTel gRPC generated code version warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="opentelemetry")

# Ensure gRPC compatibility on Windows systems with Application Control
try:
    import grpc  # type: ignore[import-untyped]  # noqa: F401
except (ImportError, Exception):
    _mock_grpc = MagicMock()
    _mock_grpc.__version__ = "1.68.0"
    for _mod in [
        "grpc",
        "grpc._compression",
        "grpc._cython",
        "grpc._cython.cygrpc",
        "grpc.aio",
    ]:
        sys.modules[_mod] = _mock_grpc

# Base paths resolved relative to this config file's location
SRC_DIR: Path = Path(__file__).resolve().parent
BASE_DIR: Path = SRC_DIR.parent
TEXTBOOKS_DIR: Path = BASE_DIR / "textbooks"
STORAGE_DIR: Path = BASE_DIR / "storage"

# Ensure essential directories exist
TEXTBOOKS_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Automatically load environment variables from .env located at BASE_DIR
ENV_FILE: Path = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# =====================================================================
# Multi-Provider Configuration
# =====================================================================

PROVIDER_GEMINI = "Google Gemini"
PROVIDER_OPENAI = "OpenAI"
PROVIDER_GROQ = "Groq"
PROVIDER_ANTHROPIC = "Anthropic Claude"
PROVIDER_CUSTOM = "Custom / OpenRouter (OpenAI-Compatible)"

SUPPORTED_PROVIDERS: Tuple[str, ...] = (
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_GROQ,
    PROVIDER_ANTHROPIC,
    PROVIDER_CUSTOM,
)

PROVIDER_MODELS: Dict[str, List[str]] = {
    PROVIDER_GEMINI: [
        "models/gemini-3.8-flash",
        "gemini-3.8-flash",
        "models/gemini-2.5-flash",
        "gemini-2.5-flash",
        "models/gemini-2.5-pro",
        "models/gemini-1.5-flash",
    ],
    PROVIDER_OPENAI: [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o1-mini",
    ],
    PROVIDER_GROQ: [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    PROVIDER_ANTHROPIC: [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    PROVIDER_CUSTOM: [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.3-70b-instruct",
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-large-2411",
    ],
}

PROVIDER_DEFAULT_MODELS: Dict[str, str] = {
    PROVIDER_GEMINI: "models/gemini-3.8-flash",
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_GROQ: "llama-3.3-70b-versatile",
    PROVIDER_ANTHROPIC: "claude-3-5-sonnet-20241022",
    PROVIDER_CUSTOM: "deepseek/deepseek-chat",
}

# Embedding Models
GEMINI_EMBED_MODELS: Tuple[str, ...] = (
    "models/gemini-embedding-2-preview",
    "gemini-embedding-2-preview",
    "models/text-embedding-004",
    "text-embedding-004",
)

OPENAI_EMBED_MODELS: Tuple[str, ...] = (
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
)

# Defaults
DEFAULT_PROVIDER: str = PROVIDER_GEMINI
LLM_MODEL: str = "models/gemini-3.8-flash"
EMBED_MODEL: str = "models/gemini-embedding-2-preview"

# Ingestion & Chunking Parameters
CHUNK_SIZE: int = 512
CHUNK_OVERLAP: int = 50

# Rate Limiting & Throttling
EMBED_BATCH_SIZE: int = 32
EMBED_DELAY_SECONDS: float = 1.5
MAX_EMBED_RETRIES: int = 5

# Similarity Top-K for retrieval
SIMILARITY_TOP_K: int = 5

# Allowed Enums for Generation
ALLOWED_DIFFICULTIES: Tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")
ALLOWED_QUESTION_TYPES: Tuple[str, ...] = ("Conceptual", "MCQs", "Numerical-Coding")


def parse_multi_keys(raw_input: str | None) -> List[str]:
    """Parse comma, semicolon, or newline-separated API keys into a list of clean tokens.

    Args:
        raw_input: Raw string containing one or multiple API keys.

    Returns:
        List of non-empty API key strings.
    """
    if not raw_input:
        return []
    # Split by commas, semicolons, or newlines
    tokens = [k.strip() for k in raw_input.replace(";", ",").replace("\n", ",").split(",") if k.strip()]
    return tokens


def get_provider_api_keys(provider: str, runtime_input: str | None = None) -> List[str]:
    """Retrieve and parse API keys for a specific provider.

    Checks explicit runtime input first (supporting multiple keys), then environment variables.

    Args:
        provider: Provider identifier (e.g., 'Google Gemini', 'OpenAI').
        runtime_input: Optional runtime key string provided via UI.

    Returns:
        List of valid API keys for the provider.
    """
    keys = parse_multi_keys(runtime_input)
    if keys:
        return keys

    env_map = {
        PROVIDER_GEMINI: ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        PROVIDER_OPENAI: ["OPENAI_API_KEY"],
        PROVIDER_GROQ: ["GROQ_API_KEY"],
        PROVIDER_ANTHROPIC: ["ANTHROPIC_API_KEY"],
        PROVIDER_CUSTOM: ["CUSTOM_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"],
    }

    env_vars = env_map.get(provider, ["GOOGLE_API_KEY"])
    for var in env_vars:
        val = os.getenv(var)
        if val and val.strip():
            parsed = parse_multi_keys(val)
            if parsed:
                return parsed

    return []


def get_api_key(runtime_key: str | None = None) -> str | None:
    """Legacy helper: Retrieve Google API Key safely.

    Args:
        runtime_key: Optional API key provided at runtime.

    Returns:
        The valid API key string if found, otherwise None.
    """
    keys = get_provider_api_keys(PROVIDER_GEMINI, runtime_key)
    return keys[0] if keys else None