"""The reveal page is static; everything it shows travels in the URL fragment
as base64url-encoded JSON.  The fragment never reaches a server, and the
encoding keeps the giftee from being readable at a glance."""

from __future__ import annotations

import base64
import json

from .assignment import display_name


def relay_prefix(config) -> str | None:
    """Optional ``relay_tag`` so several configs can share one santa inbox:
    with ``relay_tag: test`` the post addresses become ``+test-to-santa`` and
    ``+test-to-giftee`` and the relays ignore each other's letters."""
    prefix = config.get("relay_tag") if config is not None else None
    if not prefix:
        return None
    return str(prefix).strip().lower() or None


def encode_payload(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_payload(token: str) -> dict:
    token += "=" * (-len(token) % 4)
    return json.loads(base64.urlsafe_b64decode(token))


def assignment_payload(config, gifter: str, giftee: str, year: int) -> dict:
    data = {
        "g": display_name(gifter),
        "t": display_name(giftee),
        "y": year,
        "s": str(config.sender),
    }
    for key, field in (("f", "family"), ("w", "wishlist"), ("d", "deadline"), ("n", "notes")):
        value = config.get(field)
        if value:
            data[key] = str(value)
    prefix = relay_prefix(config)
    if prefix:
        data["p"] = prefix
    return data


def page_link(base: str, payload: dict) -> str:
    base = str(base)
    if not base.endswith(".html"):
        base = base.rstrip("/") + "/"
    return base + "#" + encode_payload(payload)


def assignment_link(config, gifter: str, giftee: str, year: int, base: str | None = None) -> str | None:
    base = base or config.get("page_url")
    if not base:
        return None
    return page_link(base, assignment_payload(config, gifter, giftee, year))
