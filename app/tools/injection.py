"""Deterministic screening before any email reaches a model."""

import re
import unicodedata

from app.models.schemas import InjectionReport

PATTERNS = {
    "ignore_instructions": (
        r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)"
        r"\s+(?:instructions?|prompts?|rules?)"
    ),
    "role_override": r"you\s+are\s+now\s+(?:a|an|the|in)\b",
    "role_marker": (
        r"<\|(?:system|assistant|im_start)\|>|\[/?INST\]"
        r"|(?:^|\n)\s*(?:system|developer)\s*:"
    ),
    "prompt_extraction": (
        r"(?:reveal"
        r"|print|show|repeat)\s+(?:your\s+|the\s+)?(?:system|developer)\s+prompt"
    ),
    "encoded_block": r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{120,}={0,2}(?![A-Za-z0-9+/])",
}


async def detect_injection(text: str) -> InjectionReport:
    normalized = unicodedata.normalize("NFKC", text)
    matches = [name for name, pattern in PATTERNS.items() if re.search(pattern, normalized, re.I)]
    if any(unicodedata.category(char) == "Cf" for char in text):
        matches.append("invisible_control")
    return InjectionReport(detected=bool(matches), matched_patterns=matches)
