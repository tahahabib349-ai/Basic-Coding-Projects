"""Application settings and secure API-key handling.

The API key is looked up, in order, from:
  1. A key typed into the app's sidebar for the current session (never saved).
  2. The environment variable GEMINI_API_KEY (or GOOGLE_API_KEY).
  3. A `.env` file in the project folder (GEMINI_API_KEY=...).
  4. Streamlit secrets (.streamlit/secrets.toml).

The key is never hard-coded, never written to logs, and only ever displayed
in masked form (e.g. "AIza…9Q2x").
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

KEY_ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _read_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env reader (KEY=VALUE lines) so we need no extra dependency."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_streamlit_secret(name: str) -> str | None:
    try:
        import streamlit as st

        return st.secrets.get(name)  # type: ignore[no-any-return]
    except Exception:
        # No secrets file, or not running inside Streamlit.
        return None


def find_api_key(session_key: str | None = None) -> tuple[str | None, str]:
    """Return (key, where_it_came_from). Key is None if not configured."""
    if session_key and session_key.strip():
        return session_key.strip(), "entered in the app (this session only)"
    for name in KEY_ENV_NAMES:
        if os.environ.get(name, "").strip():
            return os.environ[name].strip(), f"environment variable {name}"
    dotenv = _read_dotenv(PROJECT_ROOT / ".env")
    for name in KEY_ENV_NAMES:
        if dotenv.get(name):
            return dotenv[name], ".env file"
    for name in KEY_ENV_NAMES:
        secret = _read_streamlit_secret(name)
        if secret:
            return str(secret).strip(), "Streamlit secrets file"
    return None, "not configured"


def mask_secret(secret: str | None) -> str:
    """Show only the first 4 and last 4 characters of a secret."""
    if not secret:
        return "(none)"
    if len(secret) <= 10:
        return "•" * len(secret)
    return f"{secret[:4]}…{secret[-4:]}"


class RedactSecretsFilter(logging.Filter):
    """Logging filter that removes anything that looks like a Google API key."""

    _pattern = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")

    def __init__(self, extra_secrets: list[str] | None = None):
        super().__init__()
        self.extra = [s for s in (extra_secrets or []) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        msg = self._pattern.sub("[REDACTED-KEY]", msg)
        for secret in self.extra:
            msg = msg.replace(secret, "[REDACTED-KEY]")
        record.msg, record.args = msg, ()
        return True


def get_logger() -> logging.Logger:
    logger = logging.getLogger("ib_analyst")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        handler.addFilter(RedactSecretsFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    provider: str = os.environ.get("IBA_PROVIDER", "gemini")
    # Gemini model names change over time; override with IBA_GEMINI_MODEL.
    gemini_model: str = os.environ.get("IBA_GEMINI_MODEL", "gemini-3.5-flash")
    temperature: float = 0.1  # low = more factual, less creative
    max_output_tokens: int = _env_int("IBA_MAX_OUTPUT_TOKENS", 32_000)
    # Maximum characters of document content sent to the AI per analysis
    # (~4 characters per token). Larger material is selected intelligently.
    max_context_chars: int = _env_int("IBA_MAX_CONTEXT_CHARS", 400_000)
    max_file_mb: int = _env_int("IBA_MAX_FILE_MB", 50)
    max_pdf_pages: int = _env_int("IBA_MAX_PDF_PAGES", 600)
    max_excel_cells: int = _env_int("IBA_MAX_EXCEL_CELLS", 2_000_000)
    request_timeout_s: int = _env_int("IBA_REQUEST_TIMEOUT_S", 300)
    max_retries: int = 3
    extra: dict = field(default_factory=dict)


settings = Settings()
