from __future__ import annotations
from typing import Optional
from .client import PSAClient

_default: PSAClient | None = None


def get_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> PSAClient:
    global _default
    if api_key or base_url or kwargs:
        return PSAClient(api_key=api_key, base_url=base_url, **kwargs)
    if _default is None:
        _default = PSAClient()
    return _default
