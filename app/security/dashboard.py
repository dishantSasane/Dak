"""Shared-password protection for the single-reviewer demo dashboard."""

from __future__ import annotations

import base64
import binascii
import secrets


def valid_dashboard_authorization(header: str | None, password: str) -> bool:
    """Validate the demo's fixed reviewer account using HTTP Basic auth."""
    if not password or not header:
        return False
    scheme, separator, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not separator:
        return False
    try:
        credentials = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    username, separator, supplied_password = credentials.partition(":")
    return bool(separator) and username == "reviewer" and secrets.compare_digest(
        supplied_password, password
    )
