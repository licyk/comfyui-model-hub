"""Configuration shared by dependency setup and the extension."""

import logging
import os
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = ROOT_PATH / "requirements.txt"
LOGGER_NAME = os.getenv("COMFYUI_MODEL_HUB_LOGGER_NAME", "ComfyUI-Model-Hub")
LOGGER_LEVEL = int(os.getenv("COMFYUI_MODEL_HUB_LOGGER_LEVEL", str(logging.INFO)))
LOGGER_COLOR = os.getenv("COMFYUI_MODEL_HUB_LOGGER_COLOR", "1").lower() not in {"0", "false", "none"}


def public_base_url() -> str | None:
    """Use an administrator-supplied URL for OAuth behind a reverse proxy."""
    return os.getenv("COMFYUI_MODEL_HUB_PUBLIC_BASE_URL") or None
