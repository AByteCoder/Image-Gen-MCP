"""MCP tool definitions: generate_image and edit_image.

``image_gen_mcp.ui`` is imported first (before FastMCP is instantiated) to
ensure the Prefab UI CSP patch is applied. Do not reorder or remove that
import — it is a required side-effect import.
"""

import image_gen_mcp.ui  # noqa: F401 — must precede FastMCP() to apply CSP patch

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import ToolResult
from google.genai import types as genai_types
from pydantic import Field

from image_gen_mcp.client import client
from image_gen_mcp.config import IMAGE_MODEL
from image_gen_mcp.image_utils import _build_image_config, _collect_results, _load_image
from image_gen_mcp.types import AspectRatio, Resolution

mcp = FastMCP(
    name="image-gen-mcp",
    instructions=(
        "Generate or edit images using the Gemini image model. "
        "Images are rendered inline via Prefab UI and file paths are always returned to the LLM."
    ),
    version="0.2.0"
)


@mcp.tool(app=True)
async def generate_image(
    prompt: Annotated[str, Field(description="Text description of the image to generate.")],
    filename_prefix: Annotated[str, Field(description="Prefix for the saved filename.")] = "generated",
    aspect_ratio: Annotated[AspectRatio | None, Field(description="Output aspect ratio. Uses the model default when omitted.")] = None,
    resolution: Annotated[Resolution, Field(description="Output resolution.")] = "1K",
    ctx: Context = CurrentContext(),
) -> ToolResult:
    """Generate an image from a text prompt using the Gemini image model."""
    image_config = _build_image_config(aspect_ratio, resolution)

    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=image_config,
        ),
    )

    return await _collect_results(
        response.candidates[0].content.parts, filename_prefix, prompt, ctx
    )


@mcp.tool(app=True)
async def edit_image(
    image_path: Annotated[list[str], Field(description="Local file paths or HTTP(S) URLs of the source image(s). Multiple images can be composited or referenced together.")],
    prompt: Annotated[str, Field(description="Text description of the desired edits.")],
    filename_prefix: Annotated[str, Field(description="Prefix for the saved filename.")] = "edited",
    aspect_ratio: Annotated[AspectRatio | None, Field(description="Output aspect ratio. Uses the model default when omitted.")] = None,
    resolution: Annotated[Resolution, Field(description="Output resolution.")] = "1K",
    ctx: Context = CurrentContext(),
) -> ToolResult:
    """Edit one or more existing images using a text prompt via the Gemini image model."""
    source_images = [await _load_image(src) for src in image_path]
    image_config = _build_image_config(aspect_ratio, resolution)

    chat = client.aio.chats.create(
        model=IMAGE_MODEL,
        config=genai_types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=image_config,
        ),
    )
    response = await chat.send_message([prompt, *source_images])

    return await _collect_results(
        response.candidates[0].content.parts, filename_prefix, prompt, ctx
    )
