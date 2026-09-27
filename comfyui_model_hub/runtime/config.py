"""Configuration shared by dependency setup and the extension."""

import logging
import os
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = ROOT_PATH / "requirements.txt"
LOGGER_NAME = os.getenv("COMFYUI_MODEL_HUB_LOGGER_NAME", "Model-Hub")
LOGGER_LEVEL = int(os.getenv("COMFYUI_MODEL_HUB_LOGGER_LEVEL", str(logging.INFO)))
LOGGER_COLOR = os.getenv("COMFYUI_MODEL_HUB_LOGGER_COLOR", "1").lower() not in {"0", "false", "none"}


def public_base_url() -> str | None:
    """Use an administrator-supplied URL for OAuth behind a reverse proxy."""
    return os.getenv("COMFYUI_MODEL_HUB_PUBLIC_BASE_URL") or None


def combined_view() -> bool:
    """Pin Hub's "All folders" library entry: on unless the administrator turns it off."""
    raw = os.getenv("COMFYUI_MODEL_HUB_COMBINED_VIEW", "").strip().lower()
    if not raw or raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    logging.getLogger(LOGGER_NAME).warning("Ignoring COMFYUI_MODEL_HUB_COMBINED_VIEW=%r; use 1 or 0", raw)
    return True
