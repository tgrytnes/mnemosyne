"""
Unit tests for Story 024: email cleaning/dedup pipeline.
"""


def test_clean_body_removes_html_urls_emails_and_tracking():
    from mnemosyne.aletheia.email_cleaner import clean_email_body

    raw = """
    <html><body>
    Hello john@example.com,
    Visit https://example.com/?utm_source=test&foo=bar or www.example.org.
    Best regards,
    Sent from my iPhone
    </body></html>
    """
    cleaned = clean_email_body(raw)
    assert "john@example.com" not in cleaned
    assert "http" not in cleaned
    assert "www.example.org" not in cleaned
    assert "utm_source" not in cleaned
    assert "Sent from my iPhone" not in cleaned
    assert "Hello" in cleaned


def test_mojibake_rejection_and_truncation():
    from mnemosyne.aletheia.email_cleaner import contains_mojibake, truncate_body

    bad = "Broken umlaut Ã¼ and replacement \ufffd"
    assert contains_mojibake(bad) is True

    long_text = "a" * 9000
    truncated = truncate_body(long_text, max_chars=8000)
    assert len(truncated) == 8000
