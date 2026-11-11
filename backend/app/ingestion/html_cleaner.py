from __future__ import annotations

import re
from typing import List, Set


def clean_html(html: str) -> str:
    """Clean HTML by removing scripts, styles, nav, footer, header and normalizing whitespace."""
    # Remove script tags
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    # Remove style tags
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Remove nav elements
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL)
    # Remove footer elements
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL)
    # Remove header elements
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL)
    # Normalize whitespace
    return normalize_whitespace(html)


def strip_nav_footer_script(html: str) -> str:
    """Strip navigation, footer, script tags from HTML."""
    return clean_html(html)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse runs, trim."""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def dedupe_chunks(chunks: List["SourceChunk"]) -> List["SourceChunk"]:
    """Deduplicate chunks based on normalized text content."""
    seen: Set[str] = set()
    unique: List["SourceChunk"] = []
    for chunk in chunks:
        norm = normalize_whitespace(chunk.text)[:200]
        if norm not in seen:
            seen.add(norm)
            unique.append(chunk)
    return unique