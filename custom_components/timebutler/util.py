"""Helpers for the Timebutler integration."""

from __future__ import annotations

import hashlib


def unique_id_from_token(api_token: str) -> str:
    """Return a stable config entry unique ID that carries no token material."""
    return hashlib.sha256(api_token.encode()).hexdigest()
