"""CloudMailin inbound payload parsing and signature verification — T1.2.

Parse contract (05-api-and-ui.md §1.1 references this module):
- Verify the shared secret before trusting any payload.
- Parse provider JSON into ``ParsedEmail``.
- Derive plain text from HTML when ``plain`` is empty (agents never see raw
  HTML; emails.body_plain must hold it — 03-data-model.md §1.2).
- Fall back to a content-hash message id when the header is absent
  (message_id is the idempotency key and is NOT NULL).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

import html2text

# CloudMailin sends the raw request body signed with the account secret.
SIGNATURE_HEADER = "X-CM-Signature"


class SignatureError(ValueError):
    """Provider signature verification failed."""


@dataclass(frozen=True)
class ParsedEmail:
    sender: str
    recipient: str
    subject: str
    plain: str
    html: str
    message_id: str
    in_reply_to: str | None
    headers: dict[str, str] = field(default_factory=dict)
    unparseable: bool = False


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Constant-time HMAC comparison of the raw request body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def html_to_plain(html: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    return converter.handle(html).strip()


def _content_hash(payload: dict) -> str:
    material = "|".join(
        [
            str(payload.get("sender", "")),
            str(payload.get("subject", "")),
            str(payload.get("plain", "")),
            str(payload.get("html", "")),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"generated-{digest}@local"


def parse_payload(payload: dict) -> ParsedEmail:
    """Parse CloudMailin JSON into ParsedEmail.

    Raises ValueError on structurally unusable payloads (no sender at all);
    the webhook catches that, stores the raw payload and returns 200 per
    05-api-and-ui.md §1.1.
    """
    sender = str(payload.get("sender", "")).strip()
    if not sender:
        raise ValueError("payload has no sender")

    plain = str(payload.get("plain", "") or "")
    html = str(payload.get("html", "") or "")
    if not plain.strip() and html.strip():
        plain = html_to_plain(html)

    headers_raw = payload.get("headers", {}) or {}
    headers = {str(k): str(v) for k, v in headers_raw.items()}

    message_id = str(headers.get("message-id", "") or payload.get("message_id", "") or "").strip()
    if not message_id:
        message_id = _content_hash(payload)

    in_reply_to = str(headers.get("in-reply-to", "") or "").strip() or None

    return ParsedEmail(
        sender=sender,
        recipient=str(payload.get("recipient", "") or ""),
        subject=str(payload.get("subject", "") or ""),
        plain=plain,
        html=html,
        message_id=message_id,
        in_reply_to=in_reply_to,
        headers=headers,
    )
