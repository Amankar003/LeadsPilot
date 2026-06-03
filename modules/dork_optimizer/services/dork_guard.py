"""
Dork Guard — Dork hash generation, used dork filtering.
"""

import hashlib
import re
from modules.dork_optimizer.db_adapter import is_dork_used, get_used_dork_hashes


def generate_dork_hash(dork_text: str) -> str:
    """Generate a normalized hash for a dork string."""
    if not dork_text:
        return ""
    # Normalize: lowercase, strip, collapse whitespace
    normalized = re.sub(r"\s+", " ", dork_text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def filter_used_dorks(dorks: list[str]) -> list[str]:
    """Remove dorks that are already in dork_history."""
    if not dorks:
        return []

    used_hashes = get_used_dork_hashes()
    filtered = []
    rejected = []
    for dork in dorks:
        dork_hash = generate_dork_hash(dork)
        if dork_hash not in used_hashes:
            filtered.append(dork)
        else:
            rejected.append((dork, "already used"))
    removed = len(dorks) - len(filtered)
    if removed > 0:
        print(f"[DorkGuard] Filtered out {removed} already-used dorks: {rejected}")
    return filtered
