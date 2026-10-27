import hashlib
import hmac
import os
import subprocess
import sys

import pytest

from app.inbound.cloudmailin import parse_payload, verify_signature
from app.tokens import CROCKFORD_ALPHABET, generate_token, parse_token_from_subject


def test_token_generation_and_subject_parser() -> None:
    tokens = {generate_token() for _ in range(10_000)}
    assert len(tokens) == 10_000
    assert all(set(token[4:].replace("-", "")) <= set(CROCKFORD_ALPHABET) for token in tokens)
    assert parse_token_from_subject("Re: something [INS-7K3M-2XQ9]") == "INS-7K3M-2XQ9"
    assert parse_token_from_subject("nothing here") is None


def test_required_configuration_fails_on_import() -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "REDIS_URL", "GEMINI_API_KEY", "CLOUDMAILIN_SECRET"}
    }
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_signature_rejects_modified_body() -> None:
    body = b'{"plain":"hello"}'
    signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, "secret")
    assert not verify_signature(body + b" ", signature, "secret")
    assert not verify_signature(body, None, "secret")


def test_headers_and_html_only_payload() -> None:
    parsed = parse_payload(
        {
            "sender": "customer@example.com",
            "html": "<p>Hello <b>world</b></p>",
            "headers": {"Message-ID": "<one@example.com>", "In-Reply-To": "<parent@example.com>"},
        }
    )
    assert parsed.message_id == "<one@example.com>"
    assert parsed.in_reply_to == "<parent@example.com>"
    assert "Hello" in parsed.plain and "<p>" not in parsed.plain


def test_cloudmailin_normalized_payload() -> None:
    parsed = parse_payload(
        {
            "envelope": {"from": "customer@example.com", "to": "inbox@example.com"},
            "headers": {"message_id": "<one@example.com>", "subject": "Coverage question"},
            "plain": "Am I covered?",
        }
    )
    assert parsed.sender == "customer@example.com"
    assert parsed.recipient == "inbox@example.com"
    assert parsed.subject == "Coverage question"
    assert parsed.message_id == "<one@example.com>"


def test_missing_message_id_is_stable_and_content_sensitive() -> None:
    payload = {"sender": "customer@example.com", "plain": "hello"}
    assert parse_payload(payload).message_id == parse_payload(dict(payload)).message_id
    assert (
        parse_payload(payload).message_id != parse_payload({**payload, "plain": "bye"}).message_id
    )


@pytest.mark.parametrize("payload", [{}, {"sender": None}, {"sender": "x", "headers": []}])
def test_unusable_payload_has_explicit_parse_error(payload: dict) -> None:
    with pytest.raises(ValueError):
        parse_payload(payload)


def test_provider_authorization_uses_constant_shared_secret() -> None:
    from app.inbound.cloudmailin import verify_authorization

    assert verify_authorization("Bearer test-secret", "test-secret")
    assert not verify_authorization("Bearer wrong", "test-secret")
    assert not verify_authorization(None, "test-secret")
    assert not verify_authorization("Bearer ", "")
