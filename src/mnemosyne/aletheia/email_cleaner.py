"""Email cleaning helpers for Story 024."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def clean_email_body(raw: str) -> str:
    """Clean email body: strip HTML, URLs, emails, tracking params, signatures."""
    soup = BeautifulSoup(raw or "", "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = re.sub(r"\S+@\S+", "", text)
    text = re.sub(r"\?\S+", "", text)
    text = re.sub(r"utm_\S+", "", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    signature_patterns = [
        r"\n---\n.*",
        r"\nBest regards,.*",
        r"\nSent from my.*",
        r"\nGesendet von meinem.*",
        r"Best regards,.*",
        r"Sent from my .*",
    ]
    for pattern in signature_patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("Sent from my iPhone", "")
    text = re.sub(r"sent from my [^\n]+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_mojibake(text: str) -> bool:
    """Detect common mojibake patterns."""
    patterns = [r"Ã¼|Ã¶|Ã¤", r"\ufffd", r"â€™|â€œ|â€˜|â€�"]
    return any(re.search(p, text) for p in patterns)


def truncate_body(text: str, max_chars: int = 8000) -> str:
    """Truncate body to a max length for embedding stability."""
    return text if len(text) <= max_chars else text[:max_chars]
