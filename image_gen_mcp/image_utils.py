"""Image loading, saving, and result-collection utilities.

Provides async helpers for reading images from local paths or URLs,
persisting PIL images to disk, building GenAI image configuration objects,
and assembling ``ToolResult`` responses with inline Prefab UI rendering.
When the MCP client does not support the UI extension, results fall back
to plain-text ``file_path`` / ``url`` pairs.
"""

import asyncio
import io
from datetime import datetime
from pathlib import Path

import aiohttp
from fastmcp.server.apps import UI_EXTENSION_ID
from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from google.genai import types as genai_types
from PIL import Image as PILImage
from prefab_ui.components import Column, Image, Separator

from image_gen_mcp.config import BASE_URL, IMAGE_OUTPUT_DIR
from image_gen_mcp.types import AspectRatio, Resolution


async def _load_image(source: str) -> PILImage.Image:
    """Load a PIL image from a local file path or an HTTP(S) URL.

    Args:
        source: A local filesystem path or an ``http://`` / ``https://``
            URL pointing to an image resource.

    Returns:
        A PIL ``Image`` object loaded from ``source``.

    Raises:
        ValueError: If ``source`` is a URL whose response ``Content-Type``
            is not an ``image/*`` media type.
        FileNotFoundError: If ``source`` is a path and the file does not exist.
        aiohttp.ClientResponseError: If the HTTP request returns a non-2xx status.
    """
    if source.startswith("http://") or source.startswith("https://"):
        async with aiohttp.ClientSession() as session:
            async with session.get(source) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    raise ValueError(
                        f"URL does not point to an image (Content-Type: {content_type!r}): {source}"
                    )
                data = await resp.read()
        return PILImage.open(io.BytesIO(data))

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {source}")
    return await asyncio.to_thread(PILImage.open, path)


async def _save_pil(image: PILImage.Image, prefix: str) -> Path:
    """Save a PIL image to ``IMAGE_OUTPUT_DIR`` with a timestamped filename.

    Args:
        image: The PIL ``Image`` object to persist.
        prefix: Filename prefix. The full name is
            ``{prefix}_{YYYYmmdd_HHMMSS}.png``.

    Returns:
        The ``Path`` of the saved file.

    Raises:
        OSError: If the file cannot be written to ``IMAGE_OUTPUT_DIR``.
    """
    path = IMAGE_OUTPUT_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    await asyncio.to_thread(image.save, str(path))
    return path


def _build_image_config(
    aspect_ratio: AspectRatio | None,
    resolution: Resolution | None,
) -> genai_types.ImageConfig | None:
    """Build a GenAI ``ImageConfig`` from optional aspect ratio and resolution.

    Returns ``None`` when both arguments are falsy, which signals the GenAI
    API to use model defaults.

    Args:
        aspect_ratio: Aspect ratio string (e.g. ``"16:9"``), or ``None``.
        resolution: Resolution string (e.g. ``"1K"``), or ``None``.

    Returns:
        A ``genai_types.ImageConfig`` instance when either argument is
        provided; ``None`` otherwise.
    """
    if not aspect_ratio and not resolution:
        return None
    return genai_types.ImageConfig(
        aspect_ratio=aspect_ratio,
        image_size=resolution,
    )


async def _collect_results(
    parts,
    filename_prefix: str,
    prompt: str,
    ctx: Context,
) -> ToolResult:
    """Save image parts to disk and return a ``ToolResult``.

    Each part that carries ``inline_data`` is saved via ``_save_pil``. The
    LLM always receives file paths and serving URLs as plain text via
    ``content``. When the MCP client supports the UI extension,
    ``structured_content`` is also populated with a Prefab UI ``Column``
    for inline rendering; otherwise only plain text is returned.

    Args:
        parts: Iterable of GenAI response parts. Only parts with
            ``inline_data`` set are processed; text parts are ignored.
        filename_prefix: Prefix applied to every saved filename.
        prompt: The original generation prompt, used as image ``alt`` text.
        ctx: The FastMCP request context, used to detect UI extension support.

    Returns:
        A ``ToolResult`` whose ``content`` holds newline-separated
        ``file_path`` / ``url`` pairs and whose ``structured_content`` is
        always a dict ``{"images": [{"file_path": str, "url": str}, ...]}``.
        When the client supports the UI extension, ``structured_content`` is
        instead a Prefab UI ``Column`` for inline rendering.

    Raises:
        OSError: Propagated from ``_save_pil`` if a file cannot be written.
    """
    images: list[dict] = []

    for part in parts:
        if part.inline_data is not None:
            path = await _save_pil(part.as_image(), filename_prefix)
            images.append({
                "file_path": str(path.resolve()),
                "url": f"{BASE_URL}/images/{path.name}",
            })

    text_content = "\n\n".join(
        f"file_path: {img['file_path']}\nurl: {img['url']}" for img in images
    )
    structured: dict = {"images": images}

    if not ctx.client_supports_extension(UI_EXTENSION_ID):
        return ToolResult(content=text_content, structured_content=structured)

    with Column(gap=4, css_class="p-4") as view:
        for i, img in enumerate(images):
            if i > 0:
                Separator()
            Image(src=img["url"], alt=prompt, width="100%")

    return ToolResult(content=text_content, structured_content=view)
