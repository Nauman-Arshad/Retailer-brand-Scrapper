"""Brand name normalization and noise filtering. Noise vocabulary is configurable via API (e.g. from Google Sheets)."""
from __future__ import annotations

import re
import unicodedata

DEFAULT_NOISE_WORDS = frozenset()
DEFAULT_NOISE_PHRASES = ()
LETTER_GROUP_PATTERN = re.compile(
    r"^[A-Za-z\u00C0-\u024F]{1,3}-[A-Za-z\u00C0-\u024F]{1,3}$", re.UNICODE
)

ACTIVE_NOISE_WORDS: set[str] = set(DEFAULT_NOISE_WORDS)
ACTIVE_NOISE_PHRASES: tuple[str, ...] = tuple(DEFAULT_NOISE_PHRASES)


def configure_noise(extra_words: list[str] | None = None, extra_phrases: list[str] | None = None) -> None:
    """Set active noise vocabulary from defaults plus optional lists (e.g. from request body)."""
    global ACTIVE_NOISE_WORDS, ACTIVE_NOISE_PHRASES

    words = set(DEFAULT_NOISE_WORDS)
    if extra_words:
        for w in extra_words:
            if not isinstance(w, str):
                continue
            w = w.strip().lower()
            if w:
                words.add(w)
    ACTIVE_NOISE_WORDS = words

    phrases: list[str] = list(DEFAULT_NOISE_PHRASES)
    if extra_phrases:
        for p in extra_phrases:
            if not isinstance(p, str):
                continue
            p = p.strip().lower()
            if p:
                phrases.append(p)
    ACTIVE_NOISE_PHRASES = tuple(phrases)


def strip_emoji_and_symbols(text: str) -> str:
    """Remove emojis and disallowed symbols; keep letters, numbers, space, hyphen, apostrophe."""
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    allowed = re.compile(r"[^\w\s\-']", re.UNICODE)
    return allowed.sub("", text)


def normalize_caps(text: str) -> str:
    """Title-case; collapse whitespace."""
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.split()).title()


def is_noise_phrase(text: str) -> bool:
    """True if text looks like category/nav label, not a brand."""
    t = (text or "").strip()
    if not t or len(t) < 2:
        return True
    tl = t.lower()
    if tl in ACTIVE_NOISE_WORDS:
        return True
    for phrase in ACTIVE_NOISE_PHRASES:
        if phrase in tl:
            return True
    if LETTER_GROUP_PATTERN.match(t):
        return True
    if sum(c.isdigit() for c in tl) >= len(t) // 2:
        return True
    return False


def normalize_brand_name(raw: str) -> str:
    """Normalize and filter; returns empty string if noise."""
    s = strip_emoji_and_symbols(raw)
    s = normalize_caps(s)
    s = s.strip()
    if not s or len(s) < 2:
        return ""
    if is_noise_phrase(s):
        return ""
    return s


def dedupe_brand_names(names: list[str]) -> list[str]:
    """Return unique normalized names, order preserved; empties removed."""
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        n = normalize_brand_name(n) if isinstance(n, str) else ""
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
