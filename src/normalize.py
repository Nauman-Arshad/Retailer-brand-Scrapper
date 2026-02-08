"""
Normalize brand names: strip emojis, normalize caps, remove extra symbols/whitespace.
Ensures clean brand-only output (no product names, categories, etc.).
"""
from __future__ import annotations

import re
import unicodedata


# Single words: categories, product types, nav labels — not brand names
NOISE_WORDS = frozenset({
    "all", "brands", "designers", "shop", "view", "see", "more", "new", "sale",
    "women", "men", "kids", "accessories", "shoes", "bags", "beauty", "home",
    "collection", "bestseller", "trending", "clear", "filter", "sort",
    "products", "items", "clothing", "tops", "bottoms", "dresses", "outerwear",
    "swimwear", "loungewear", "intimates", "heels", "boots", "sandals", "sneakers",
    "loafers", "socks", "jewelry", "belts", "scarves", "sunglasses", "rompers",
    "jumpsuits", "arrivals", "chance", "apply", "products",
    "ana", "sayfa",  # Turkish: Ana Sayfa = Home Page
})

# Letter-group links (e.g. "A-Z", "C-Ç", "I-I", "O-Ö") — alphabet filter, not brands
LETTER_GROUP_PATTERN = re.compile(
    r"^[A-Za-z\u00C0-\u024F]{1,3}-[A-Za-z\u00C0-\u024F]{1,3}$", re.UNICODE
)

# Phrases (substring match, case-insensitive) to drop — nav/category labels
NOISE_PHRASES = (
    "ana sayfa",  # Turkish: Home Page
    "new arrivals", "sale by brands", "shop by brand", "last chance",
    "sale items", "sale clothing", "sale shoes", "sale sweaters", "sale dress",
    "shop the look", "denim jean sale", "leather sale", "swim sale", "coat sale",
    "dress sale", "shoe sale", "winter dress collection", "summer dress sale",
    "summer shoe sale", "the blazer edit", "the boot shop", "the scarf edit",
    "the valentine", "conditions apply", "hot for summer", "off the beaten track",
    "printed artworks", "solid striped", "sale fw", " front", " edit",
    "date shoes", "products", "sale fw ", "on sale", " shop",
)


def strip_emoji_and_symbols(text: str) -> str:
    """Remove emojis and non-letter symbols, keep letters, numbers, spaces, hyphen, apostrophe."""
    if not text or not isinstance(text, str):
        return ""
    # Normalize unicode (e.g. composed chars)
    text = unicodedata.normalize("NFKC", text)
    # Allow: letters, numbers, space, hyphen, apostrophe
    allowed = re.compile(r"[^\w\s\-']", re.UNICODE)
    return allowed.sub("", text)


def normalize_caps(text: str) -> str:
    """Title-case for display; strip extra whitespace."""
    if not text or not isinstance(text, str):
        return ""
    # Collapse whitespace and strip
    text = " ".join(text.split())
    # Title case (handles "MCQUEEN" -> "Mcqueen"; we can refine for known brands later)
    return text.title()


def is_noise_phrase(text: str) -> bool:
    """True if text looks like a category/nav label, not a brand name."""
    t = (text or "").strip()
    if not t or len(t) < 2:
        return True
    tl = t.lower()
    if tl in NOISE_WORDS:
        return True
    for phrase in NOISE_PHRASES:
        if phrase in tl:
            return True
    # Letter-group links (e.g. "C-Ç", "I-I", "O-Ö", "A-Z") — alphabet filter
    if LETTER_GROUP_PATTERN.match(t):
        return True
    # Drop if it's mostly numbers (e.g. "Last Chance 50")
    if sum(c.isdigit() for c in tl) >= len(t) // 2:
        return True
    return False


def normalize_brand_name(raw: str) -> str:
    """
    Full normalization: strip emoji/symbols, normalize caps, collapse spaces.
    Returns empty string if result looks like noise (category, product type, nav label).
    """
    s = strip_emoji_and_symbols(raw)
    s = normalize_caps(s)
    s = s.strip()
    if not s or len(s) < 2:
        return ""
    if is_noise_phrase(s):
        return ""
    return s


def dedupe_brand_names(names: list[str]) -> list[str]:
    """Return unique brand names preserving order; empty strings removed."""
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        n = normalize_brand_name(n) if isinstance(n, str) else ""
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
