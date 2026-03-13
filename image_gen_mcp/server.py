"""MCP server entry point supporting stdio and HTTP transport modes.

In **stdio** mode a minimal FastAPI static-file server runs in a daemon
thread (serving ``/images``) while the MCP session communicates over
stdin/stdout. All uvicorn output is redirected to stderr so that stdout
remains clean for JSON-RPC.

In **http** mode a single uvicorn process serves the MCP endpoint, static
image files, and a ``/health`` check on the configured ``HOST:PORT``.
"""

import argparse
import os
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from image_gen_mcp.config import HOST, IMAGE_OUTPUT_DIR, MCP_PATH, PORT
from image_gen_mcp.tools import mcp


def main() -> None:
    """Parse CLI arguments and start the server in stdio or HTTP mode.

    The ``--transport`` flag takes precedence over the ``MCP_TRANSPORT``
    environment variable. When neither is provided, the default is
    ``'stdio'``.

    Args:
        None. Arguments are read from ``sys.argv`` via ``argparse``.

    Returns:
        None

    Raises:
        SystemExit: If ``argparse`` receives unrecognised arguments.
    """
    parser = argparse.ArgumentParser(prog="image-gen-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (overrides MCP_TRANSPORT env var)",
    )
    args = parser.parse_args()
    transport = args.transport or os.environ.get("MCP_TRANSPORT", "http")

    if transport == "stdio":
        _run_stdio()
    else:
        _run_http()


def _run_stdio() -> None:
    """Start the server in stdio transport mode.

    Launches a minimal FastAPI image-serving process in a daemon thread,
    then hands control to the MCP stdio runner. Shuts down the image
    server cleanly when the MCP client closes the pipe.

    Returns:
        None
    """
    image_app = FastAPI(title="Image Static Server")

    @image_app.get("/health")
    async def _health() -> dict:
        return {"status": "ok"}

    image_app.mount(
        "/images",
        StaticFiles(directory=str(IMAGE_OUTPUT_DIR.resolve())),
        name="images",
    )

    # Route all uvicorn output to stderr — stdout is reserved for MCP JSON-RPC.
    _stderr_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": False,
            },
        },
        "handlers": {
            "stderr": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn":        {"handlers": ["stderr"], "level": "WARNING", "propagate": False},
            "uvicorn.error":  {"handlers": ["stderr"], "level": "WARNING", "propagate": False},
            "uvicorn.access": {"handlers": [],          "level": "WARNING", "propagate": False},
        },
    }

    image_server = uvicorn.Server(
        uvicorn.Config(
            image_app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=_stderr_log_config,
            ws="websockets-sansio",
        )
    )
    thread = threading.Thread(target=image_server.run, daemon=True)
    thread.start()

    try:
        mcp.run()  # blocks on stdin; exits when MCP client closes the pipe
    finally:
        image_server.should_exit = True
        thread.join(timeout=5)


def _run_http() -> None:
    """Start the server in HTTP transport mode.

    Mounts the MCP ASGI app, static image files, and a health endpoint on
    a single FastAPI application and serves it with uvicorn.

    Returns:
        None
    """
    mcp_app = mcp.http_app(path="/")

    app = FastAPI(title="Image Gen MCP", lifespan=mcp_app.lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.mount("/images", StaticFiles(directory=str(IMAGE_OUTPUT_DIR.resolve())), name="images")
    app.mount(MCP_PATH, mcp_app)

    uvicorn.run(app, host=HOST, port=PORT, ws="websockets-sansio")
