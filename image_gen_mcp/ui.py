"""Prefab UI Content Security Policy patching.

This module patches ``prefab_ui.renderer.get_renderer_csp`` to whitelist
``BASE_URL`` as an allowed resource domain, enabling inline image rendering
from the local image-serving endpoint.

The patch is applied automatically when this module is imported. It must
be imported before ``FastMCP`` is instantiated — see ``tools.py``.
"""

import prefab_ui.renderer

from image_gen_mcp.config import BASE_URL

_original_get_renderer_csp = prefab_ui.renderer.get_renderer_csp


def _apply_csp_patch() -> None:
    """Patch prefab_ui renderer CSP to allow images served from BASE_URL.

    Replaces ``prefab_ui.renderer.get_renderer_csp`` with a wrapper that
    appends ``BASE_URL`` to the ``resource_domains`` list returned by the
    original function. Safe to call multiple times — the set() deduplicates.

    Returns:
        None
    """
    def _patched_get_renderer_csp() -> dict:
        data = _original_get_renderer_csp()
        if isinstance(data, dict) and "resource_domains" in data:
            data["resource_domains"] = list(set(data["resource_domains"] + [BASE_URL]))
        return data

    prefab_ui.renderer.get_renderer_csp = _patched_get_renderer_csp


_apply_csp_patch()
