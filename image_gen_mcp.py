"""
Image Gen MCP — FastMCP stdio server for image generation and editing using Google GenAI.

Environment variables:
  GEMINI_API_KEY          - Your Google Gemini API key (required, or use service account)
  GOOGLE_SERVICE_ACCOUNT_FILE - Path to a Google service account JSON key file (alternative to API key)
  GOOGLE_VERTEX_LOCATION  - Vertex AI location when authenticating via service account (optional, defaults to 'global')
  IMAGE_OUTPUT_DIR        - Directory to save generated/edited images (optional, defaults to ./images)
  IMAGE_MODEL             - Gemini model to use (optional, defaults to gemini-3.1-flash-image-preview)
  RETURN_FILEPATH         - Set to '1' or 'true' to return file paths instead of image content in tool responses
"""

import io
import os
from pathlib import Path
from datetime import datetime
from typing import Literal
from pydantic import Field

import aiohttp
import mcp.types as types
from google import genai
from google.genai import types as genai_types
from google.oauth2 import service_account
from PIL import Image as PILImage

from fastmcp import FastMCP
from fastmcp.utilities.types import Image


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")

if not GEMINI_API_KEY and not SERVICE_ACCOUNT_FILE:
    raise EnvironmentError(
        "Neither GEMINI_API_KEY nor GOOGLE_SERVICE_ACCOUNT_FILE environment variable is set. "
        "Export one before starting the server:\n"
        "  export GEMINI_API_KEY=your_api_key_here\n"
        "  or\n"
        "  export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service_account_key.json"
    )

IMAGE_OUTPUT_DIR = Path(os.environ.get("IMAGE_OUTPUT_DIR", "./images"))
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-image-preview")

RETURN_FILEPATH = os.environ.get("RETURN_FILEPATH", "").lower() in ("1", "true")

if SERVICE_ACCOUNT_FILE:
    _credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    _vertex_location = os.environ.get("GOOGLE_VERTEX_LOCATION", "global")
    client = genai.Client(credentials=_credentials, vertexai=True, project=_credentials.project_id, location=_vertex_location)
else:
    client = genai.Client(api_key=GEMINI_API_KEY)


mcp = FastMCP(
    name="image-gen-mcp",
    instructions=(
        "Generate or edit images using the Gemini image model. "
        "Images are returned inline by default, or as file paths when RETURN_FILEPATH is set."
    ),
)


@mcp.resource("images://{image_id}", mime_type="image/png")
async def get_image(image_id: str) -> bytes:
    """Serve a generated image by ID (basename without extension)."""
    candidate = IMAGE_OUTPUT_DIR / f"{image_id}.png"
    if not candidate.exists():
        raise ValueError(f"Image not found: {image_id}")
    return candidate.read_bytes()


async def _load_image(source: str) -> PILImage.Image:
    """Load a PIL image from a file path or HTTP(S) URL."""
    if source.startswith("http://") or source.startswith("https://"):
        async with aiohttp.ClientSession() as session:
            async with session.get(source) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    raise ValueError(f"URL does not point to an image (Content-Type: {content_type!r}): {source}")
                data = await resp.read()
        return PILImage.open(io.BytesIO(data))
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {source}")
    return PILImage.open(path)


def _save_pil(image: PILImage.Image, prefix: str) -> Path:
    path = IMAGE_OUTPUT_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    image.save(str(path))
    return path


def _collect_results(parts, filename_prefix: str) -> list[types.ContentBlock]:
    """Save each image part and return MCP content blocks."""
    results = []
    for part in parts:
        if part.inline_data is not None:
            path = _save_pil(part.as_image(), filename_prefix)
            image_id = path.stem
            results.append(
                Image(
                    path=str(path.resolve()),
                    format="png",
                )
            )
            if RETURN_FILEPATH:
                results.append(
                    types.TextContent(
                        type="text",
                        text=f"resource_id: images://{image_id}\nfile_path: {path.resolve()}",
                    )
                )
    return results


AspectRatio = Literal[
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3",
    "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
]

Resolution = Literal["512px", "1K", "2K", "4K"]


@mcp.tool()
async def generate_image(
    prompt: str,
    filename_prefix: str = "generated",
    aspect_ratio: AspectRatio | None = None,
    resolution: Resolution = "1K"
) -> list[types.ContentBlock]:
    """Generate an image from a text prompt using the Gemini image model.

    Args:
        prompt: Text description of the image to generate.
        filename_prefix: Optional prefix for the saved filename (default: 'generated').
        aspect_ratio: Optional aspect ratio for the generated image.
        resolution: Optional resolution for the generated image.
    """
    image_config = genai_types.ImageConfig(
        aspect_ratio=aspect_ratio,
        image_size=resolution,
    ) if (aspect_ratio or resolution) else None

    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=image_config,
        ),
    )

    return _collect_results(response.candidates[0].content.parts, filename_prefix)


@mcp.tool()
async def edit_image(
    image_path: list[str],
    prompt: str,
    filename_prefix: str = "edited",
    aspect_ratio: AspectRatio | None = None,
    resolution: Resolution = "1K"
) -> list[types.ContentBlock]:
    """Edit one or more existing images using a text prompt via the Gemini image model.

    Args:
        image_path: List of absolute paths to the source image file(s). Multiple
                    images can be provided to composite or reference several sources.
        prompt: Text description of the desired edits.
        filename_prefix: Optional prefix for the saved filename (default: 'edited').
        aspect_ratio: Optional aspect ratio for the output image.
        resolution: Optional resolution for the output image.
    """
    source_images = [await _load_image(src) for src in image_path]

    image_config = genai_types.ImageConfig(
        aspect_ratio=aspect_ratio,
        image_size=resolution,
    ) if (aspect_ratio or resolution) else None

    chat = client.aio.chats.create(
        model=IMAGE_MODEL,
        config=genai_types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=image_config,
        ),
    )
    response = await chat.send_message([prompt, *source_images])

    return _collect_results(response.candidates[0].content.parts, filename_prefix)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
