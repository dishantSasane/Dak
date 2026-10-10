"""Case token generation and parsing — 03-data-model.md §1.1, T1.1.

Crockford Base32 alphabet: 0123456789ABCDEFGHJKMNPQRSTVWXYZ
(excludes I, L, O, U). Format INS-XXXX-XXXX, 8 random characters from
secrets.choice. Never sequential.
"""

from __future__ import annotations

import re
import secrets

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

TOKEN_RE = re.compile(r"\[INS-([0-9A-HJKMNP-TV-Z]{4})-([0-9A-HJKMNP-TV-Z]{4})\]")


def generate_token() -> str:
    """Return a new case token like ``INS-7K3M-2XQ9``."""
    chars = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(8))
    return f"INS-{chars[:4]}-{chars[4:]}"


def parse_token_from_subject(subject: str) -> str | None:
    """Extract a case token from a subject line, or None if absent.

    Matches the architecture regex ``\\[INS-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}\\]``
    (02-architecture.md §1.1 step 3a). Input is upper-cased first so tokens
    typed in lower case still match; Crockford's alphabet has no lower-case
    ambiguity issues for our purposes.
    """
    match = TOKEN_RE.search(subject.upper())
    if match is None:
        return None
    return f"INS-{match.group(1)}-{match.group(2)}"
