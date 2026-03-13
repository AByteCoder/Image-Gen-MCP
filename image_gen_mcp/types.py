"""Type aliases for image generation parameters."""

from typing import Literal

AspectRatio = Literal[
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3",
    "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
]

Resolution = Literal["512px", "1K", "2K", "4K"]
