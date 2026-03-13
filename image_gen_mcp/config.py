"""Runtime configuration loaded from environment variables.

All values are read once at import time. Any module that needs configuration
should import the constants directly from this module.

Environment Variables:
    GEMINI_API_KEY: Google Gemini API key. Required unless
        GOOGLE_SERVICE_ACCOUNT_FILE is set.
    GOOGLE_SERVICE_ACCOUNT_FILE: Path to a Google service account JSON key
        file. Alternative to GEMINI_API_KEY for Vertex AI authentication.
    GOOGLE_VERTEX_LOCATION: Vertex AI location when authenticating via
        service account. Defaults to ``'global'``.
    IMAGE_OUTPUT_DIR: Directory where generated/edited images are saved.
        Defaults to ``'./images'``. Created automatically if absent.
    IMAGE_MODEL: Gemini model identifier to use for image generation.
        Defaults to ``'gemini-3.1-flash-image-preview'``.
    HOST: Bind address for the HTTP server. Defaults to ``'0.0.0.0'``.
    PORT: Listen port for the HTTP server. Defaults to ``56789``.
    BASE_URL: Public base URL used to build image serving URLs.
        Defaults to ``'http://localhost:{PORT}'``.
    MCP_PATH: Mount path for the MCP endpoint. Defaults to ``'/mcp'``.
    MCP_TRANSPORT: Default transport mode when ``--transport`` CLI flag is
        absent. One of ``'stdio'`` or ``'http'``. Defaults to ``'http'``.

Raises:
    EnvironmentError: If neither GEMINI_API_KEY nor
        GOOGLE_SERVICE_ACCOUNT_FILE is set.
"""

import os
from pathlib import Path

HOST: str = os.environ.get("HOST", "0.0.0.0")
PORT: int = int(os.environ.get("PORT", "56789"))
BASE_URL: str = os.environ.get("BASE_URL", f"http://localhost:{PORT}")
MCP_PATH: str = os.environ.get("MCP_PATH", "/mcp")

GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
SERVICE_ACCOUNT_FILE: str | None = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")

if not GEMINI_API_KEY and not SERVICE_ACCOUNT_FILE:
    raise EnvironmentError(
        "Neither GEMINI_API_KEY nor GOOGLE_SERVICE_ACCOUNT_FILE environment variable is set. "
        "Export one before starting the server:\n"
        "  export GEMINI_API_KEY=your_api_key_here\n"
        "  or\n"
        "  export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service_account_key.json"
    )

IMAGE_OUTPUT_DIR: Path = Path(os.environ.get("IMAGE_OUTPUT_DIR", "./images"))
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_MODEL: str = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-image-preview")
VERTEX_LOCATION: str = os.environ.get("GOOGLE_VERTEX_LOCATION", "global")
