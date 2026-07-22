from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter


def normalize_listing_text(title: str, description: str) -> str:
    """Create a locale-independent representation for duplicate comparison."""
    normalized = unicodedata.normalize("NFKC", f"{title}\n{description}").casefold()
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9äöüß]+", " ", normalized)
    return " ".join(normalized.split())


def listing_text_fingerprint(title: str, description: str) -> str:
    normalized = normalize_listing_text(title, description)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def listing_text_similarity(
    first_title: str,
    first_description: str,
    second_title: str,
    second_description: str,
) -> float:
    first_normalized = normalize_listing_text(first_title, first_description)
    second_normalized = normalize_listing_text(second_title, second_description)
    first_tokens = first_normalized.split()
    second_tokens = second_normalized.split()
    if min(len(first_tokens), len(second_tokens)) < 8:
        return 0.0

    def shingles(tokens: list[str]) -> set[tuple[str, ...]]:
        return {tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)}

    first = shingles(first_tokens)
    second = shingles(second_tokens)
    union = first | second
    shingle_similarity = len(first & second) / len(union) if union else 0.0
    first_counts = Counter(first_tokens)
    second_counts = Counter(second_tokens)
    common_tokens = sum((first_counts & second_counts).values())
    token_similarity = 2 * common_tokens / (len(first_tokens) + len(second_tokens))
    return max(shingle_similarity, token_similarity)
