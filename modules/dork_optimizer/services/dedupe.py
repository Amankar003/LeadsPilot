"""
Deduplication — Source hash, trend dedup, recommendation fingerprint.
"""

import hashlib


def generate_source_hash(item: dict) -> str:
    """
    Generate unique hash for a source item.
    Uses: url + title + published_at + source_name
    If url is missing: title + source_name + published_at
    """
    url = (item.get("url") or "").strip()
    title = (item.get("title") or "").strip().lower()
    published_at = (item.get("published_at") or "").strip()
    source_name = (item.get("source_name") or "").strip().lower()

    if url:
        raw = f"{url}|{title}|{published_at}|{source_name}"
    else:
        raw = f"{title}|{source_name}|{published_at}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_fingerprint(trend_name: str, country: str, region: str, sector: str, recommended_service: str) -> str:
    """
    Generate unique fingerprint for a recommendation.
    Uses: trend_name + country + region + sector + recommended_service
    """
    raw = "|".join([
        (trend_name or "").strip().lower(),
        (country or "").strip().lower(),
        (region or "").strip().lower(),
        (sector or "").strip().lower(),
        (recommended_service or "").strip().lower(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
