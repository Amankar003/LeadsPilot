"""
speed_auditor.py — Measures basic website speed metrics.
Uses HTTP-based timing (no browser needed). Optionally uses Google PageSpeed API.
"""
import time
import httpx
from utils.logging_utils import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}


def audit_speed(url: str, page_size_bytes: int = 0, load_time_ms: float = 0) -> dict:
    """
    Measure basic website speed. Uses data from website_detector if available,
    otherwise performs its own request.
    """
    result = {
        "load_time_ms": load_time_ms,
        "ttfb_ms": 0,
        "page_size_bytes": page_size_bytes,
        "page_size_kb": round(page_size_bytes / 1024, 1) if page_size_bytes else 0,
        "speed_rating": "unknown",  # fast / average / slow
        "issues": [],
    }

    # If we don't have pre-fetched data, measure now
    if load_time_ms <= 0:
        try:
            start = time.time()
            with httpx.Client(
                follow_redirects=True,
                timeout=15.0,
                headers=HEADERS,
            ) as client:
                resp = client.get(url)

            total_ms = (time.time() - start) * 1000
            result["load_time_ms"] = round(total_ms, 1)
            result["page_size_bytes"] = len(resp.content)
            result["page_size_kb"] = round(len(resp.content) / 1024, 1)

        except Exception as e:
            logger.warning(f"Speed check failed for {url}: {e}")
            result["issues"].append(f"Could not measure speed: {e}")
            return result

    # ── TTFB measurement (separate HEAD request) ──
    try:
        start = time.time()
        with httpx.Client(follow_redirects=True, timeout=10.0, headers=HEADERS) as client:
            resp = client.head(url)
        result["ttfb_ms"] = round((time.time() - start) * 1000, 1)
    except Exception:
        # HEAD might be blocked, try GET with stream
        try:
            start = time.time()
            with httpx.Client(follow_redirects=True, timeout=10.0, headers=HEADERS) as client:
                with client.stream("GET", url) as resp:
                    # Read just the first chunk for TTFB
                    for _ in resp.iter_bytes(1024):
                        break
            result["ttfb_ms"] = round((time.time() - start) * 1000, 1)
        except Exception:
            pass

    # ── Rating ──
    lt = result["load_time_ms"]
    if lt > 0:
        if lt < 2000:
            result["speed_rating"] = "fast"
        elif lt < 5000:
            result["speed_rating"] = "average"
        else:
            result["speed_rating"] = "slow"

    # ── Issues ──
    if result["page_size_kb"] > 3000:
        result["issues"].append(
            f"Very large page size ({result['page_size_kb']} KB). Consider optimizing images and scripts."
        )
    elif result["page_size_kb"] > 1500:
        result["issues"].append(
            f"Large page size ({result['page_size_kb']} KB). Some optimization may help."
        )

    if result["load_time_ms"] > 5000:
        result["issues"].append(
            f"Slow load time ({round(result['load_time_ms']/1000, 1)}s). Users may abandon before page loads."
        )
    elif result["load_time_ms"] > 3000:
        result["issues"].append(
            f"Average load time ({round(result['load_time_ms']/1000, 1)}s). Room for improvement."
        )

    if result["ttfb_ms"] > 1500:
        result["issues"].append(
            f"High TTFB ({round(result['ttfb_ms']/1000, 1)}s). Server response is slow."
        )

    return result
