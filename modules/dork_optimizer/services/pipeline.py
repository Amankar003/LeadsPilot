"""
Pipeline — Main daily pipeline orchestrator.

Simple linear flow:
  sources → save → trend analysis → dork generation → save recommendations
"""

from modules.dork_optimizer.sources.gdelt_source import fetch_gdelt_data
from modules.dork_optimizer.sources.news_source import fetch_news_data
from modules.dork_optimizer.sources.rss_source import fetch_rss_data
from modules.dork_optimizer.sources.pytrends_source import fetch_pytrends_data
from modules.dork_optimizer.sources.seed_source import fetch_seed_data
from modules.dork_optimizer.trend_analyzer import analyze_trends
from modules.dork_optimizer.dork_generator import generate_dorks_for_trend
from modules.dork_optimizer.services.dork_guard import filter_used_dorks
from modules.dork_optimizer.services.market_filter import is_india_market
from modules.dork_optimizer.db_adapter import (
    save_source_data,
    get_today_source_data,
    save_trend_analysis,
    save_recommendation,
    get_today_recommendations,
    save_pipeline_status,
)


def run_daily_pipeline() -> dict:
    """
    Execute the full daily pipeline.

    Returns dict with:
      - source_stats: how many items fetched per source
      - trend_count: how many trends identified
      - recommendation_count: how many recommendations saved
      - recommendations: list of today's recommendations
    """
    save_pipeline_status("running", "Pipeline is currently executing...")

    print("\n" + "=" * 60)
    print("RUNNING DAILY PIPELINE")
    print("=" * 60)

    # ── Step 1: Collect from all live sources ────────────────
    print("\n[Step 1] Collecting from live sources...")
    all_items = []
    used_seed = False

    gdelt_items = fetch_gdelt_data()
    all_items += gdelt_items

    news_items = fetch_news_data()
    all_items += news_items

    rss_items = fetch_rss_data()
    all_items += rss_items

    pytrends_items = fetch_pytrends_data()
    all_items += pytrends_items

    # ── Step 2: Seed fallback if no live data ────────────────
    if not all_items:
        print("[Step 2] No live data — using seed fallback")
        all_items = fetch_seed_data()
        used_seed = True
    else:
        print(f"[Step 2] Got {len(all_items)} live items — skipping seed data")

    source_stats = {
        "gdelt": len(gdelt_items),
        "news": len(news_items),
        "rss": len(rss_items),
        "pytrends": len(pytrends_items),
        "seed": len(all_items) if used_seed else 0,
        "total": len(all_items),
        "used_seed": used_seed,
    }
    print(f"[Step 2] Source stats: {source_stats}")

    # ── Step 3: Save source data ─────────────────────────────
    print("\n[Step 3] Saving source data...")
    insert_stats = save_source_data(all_items)
    print(f"[Step 3] Inserted: {insert_stats['inserted']}, Skipped: {insert_stats['skipped']}")

    # ── Step 4: Get today's fresh source data ────────────────
    print("\n[Step 4] Getting today's fresh data...")
    fresh_data = get_today_source_data()
    print(f"[Step 4] Fresh items: {len(fresh_data)}")

    if not fresh_data:
        print("[Step 4] No fresh data for today — pipeline complete")
        return {
            "source_stats": source_stats,
            "trend_count": 0,
            "recommendation_count": 0,
            "recommendations": [],
        }

    # ── Step 5: Send to LLM-1 for trend analysis ────────────
    print("\n[Step 5] Analyzing trends with LLM-1...")
    try:
        trends = analyze_trends(fresh_data)
        print(f"[Step 5] Identified {len(trends)} trends")
    except Exception as e:
        print(f"[Step 5] TrendAnalyzer failed: {e}")
        save_pipeline_status(
            "llm_failed",
            f"Live data fetched, but LLM analysis failed. Check API key/provider config. (Error: {str(e)[:200]})"
        )
        trends = []

    if not trends:
        print("[Step 5] No trends identified — pipeline complete")
        return {
            "source_stats": source_stats,
            "trend_count": 0,
            "recommendation_count": 0,
            "recommendations": [],
        }

    # ── Step 6: Save trend analysis ──────────────────────────
    print("\n[Step 6] Saving trend analysis...")
    saved_trends = save_trend_analysis(trends)
    print(f"[Step 6] Saved {len(saved_trends)} trends")

    # ── Step 7-9: Generate dorks for each trend ──────────────
    print("\n[Step 7-9] Generating dorks for each trend...")
    recommendation_count = 0

    for i, trend in enumerate(saved_trends, 1):
        print(f"\n  [{i}/{len(saved_trends)}] {trend.get('trend_name', 'Unknown')}")

        # Skip any India trend before calling DorkGenerator
        if is_india_market(trend):
            print("    Skipping India trend.")
            continue

        # Step 7: LLM-2 generates dorks
        dork_output = generate_dorks_for_trend(trend)

        # Skip if DorkGenerator returns skipped=true
        if dork_output.get("skipped") is True:
            print("    Skipping: DorkGenerator flagged this as an India market trend.")
            continue

        # Step 8: Filter already-used dorks
        original_dorks = dork_output.get("dorks", [])
        print(f"    [Debug] Raw dorks count: {len(original_dorks)}")
        
        # Filter out dorks targeting Indian domains only (site:.in)
        # Note: do NOT filter "-india" which is a negative exclusion operator in dorks
        clean_dorks = [d for d in original_dorks if "site:.in" not in d.lower()]
        
        filtered_dorks = filter_used_dorks(clean_dorks)
        
        # ── Fallback safety: if filtered becomes empty but raw dorks exist, use raw ──
        if not filtered_dorks and original_dorks:
            print("    [Fallback] All dorks filtered out — using original dorks directly.")
            filtered_dorks = original_dorks[:20]
        
        dork_output["dorks"] = filtered_dorks
        
        # Filter why_this_dork to match active dorks
        why_this_dork = dork_output.get("why_this_dork", [])
        if why_this_dork:
            why_this_dork = [w for w in why_this_dork if isinstance(w, dict) and "dork" in w and "site:.in" not in w["dork"].lower()]
            dork_output["why_this_dork"] = why_this_dork

        print(f"    [Debug] Final dorks count: {len(filtered_dorks)}")

        # Do not save empty dorks
        if not filtered_dorks:
            print("    Skipping: no active dorks left.")
            continue

        # Determine status
        status = "ready"
        if used_seed:
            status = "demo"

        # Step 9: Save recommendation
        rec = {
            "trend_id": trend.get("id"),
            "trend_name": trend.get("trend_name", ""),
            "country": trend.get("country", ""),
            "region": trend.get("region", ""),
            "sector": trend.get("sector", ""),
            "domain": trend.get("domain", ""),
            "recommended_service": trend.get("recommended_service", ""),
            "keywords": dork_output.get("keywords", []),
            "dorks": filtered_dorks,
            "urls": dork_output.get("urls", []),
            "why_this_dork": dork_output.get("why_this_dork", []),
            "opportunity_score": dork_output.get("opportunity_score", 70),
            "status": status,
        }
        save_recommendation(rec)
        recommendation_count += 1
        print(f"    [Debug] Saved recommendation #{recommendation_count}")

    # ── Step 10: Return today's recommendations ──────────────
    print(f"\n[Step 10] Pipeline complete. {recommendation_count} recommendations saved.")
    recommendations = get_today_recommendations()

    save_pipeline_status("success", "")

    return {
        "source_stats": source_stats,
        "trend_count": len(saved_trends),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
    }

def run_pipeline() -> dict:
    """
    Compatibility wrapper for dork_intelligence_ui.py.
    Calls run_daily_pipeline() and remaps the output to the expected keys.
    """
    summary = run_daily_pipeline()
    return {
        "sources_processed": summary.get("source_stats", {}).get("total", 0),
        "trends_analyzed": summary.get("trend_count", 0),
        "recommendations_generated": summary.get("recommendation_count", 0)
    }
