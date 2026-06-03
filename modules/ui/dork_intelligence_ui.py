import streamlit as st
import pandas as pd
from modules.dork_optimizer.db_adapter import (
    get_today_source_data,
    get_today_trends,
    get_today_recommendations,
    get_pipeline_status,
    get_source_summary
)
from modules.dork_optimizer.services.pipeline import run_pipeline

def render_dork_intelligence_dashboard():
    st.markdown("## 🧠 Dork Intelligence Engine")
    st.caption("Standalone Intelligence Engine Parity Dashboard")
    
    # Header & Status
    status_info = get_pipeline_status()
    st.info(f"Pipeline Status: **{status_info['status']}** | {status_info['message']}")
    
    if st.button("▶ Run Full Pipeline (Sources -> Trends -> Dorks)", type="primary"):
        with st.spinner("Running full intelligence pipeline..."):
            try:
                summary = run_pipeline()
                st.success(f"Pipeline completed! Sources: {summary['sources_processed']} | Trends: {summary['trends_analyzed']} | Recommendations: {summary['recommendations_generated']}")
                st.rerun()
            except Exception as e:
                st.error(f"Pipeline failed: {e}")

    section = st.radio("Dashboard Sections", ["📊 Market Trends", "📌 Dork Recommendations", "🌐 Source Data"], horizontal=True)

    if section == "📊 Market Trends":
        st.markdown("### Today's Trend Analysis")
        trends = get_today_trends()
        if not trends:
            st.info("No trends analyzed today.")
        else:
            for t in trends:
                with st.expander(f"{t['trend_name']} - {t['country']} (Score: {t['confidence_score']})"):
                    st.write(f"**Region/Sector:** {t['region']} / {t['sector']}")
                    st.write(f"**Why this region:** {t['why_this_region']}")
                    st.write(f"**Why this sector:** {t['why_this_sector']}")
                    st.write(f"**Recommended Service:** {t['recommended_service']}")
                    if t.get("business_requirements"):
                        st.write("**Requirements:**")
                        for req in t['business_requirements']:
                            st.write(f"- {req}")

    elif section == "📌 Dork Recommendations":
        st.markdown("### High-Value Dork Recommendations")
        recs = get_today_recommendations()
        if not recs:
            st.info("No recommendations generated today.")
        else:
            # We will show them in a DataFrame for easy copy-pasting
            rec_data = []
            for r in recs:
                for d in r.get('dorks', []):
                    rec_data.append({
                        "Trend": r['trend_name'],
                        "Country": r['country'],
                        "Service": r['recommended_service'],
                        "Dork": d,
                        "Score": r['opportunity_score']
                    })
            
            if rec_data:
                df = pd.DataFrame(rec_data)
                st.dataframe(df, use_container_width=True)
                
                st.markdown("#### 📋 Copy All Generated Dorks")
                all_dorks = "\n".join([r['Dork'] for r in rec_data])
                st.code(all_dorks, language="text")
                st.info("Hover over the block above and click the copy icon in the top right to copy all dorks.")

    elif section == "🌐 Source Data":
        st.markdown("### Raw Aggregated Sources")
        summary = get_source_summary()
        st.write(f"**Total Today:** {summary['total_today']}")
        st.write(f"**By Source:** {summary['by_source']}")
        
        sources = get_today_source_data()
        if not sources:
            st.info("No source data fetched today.")
        else:
            df_src = pd.DataFrame(sources)
            st.dataframe(df_src[['source_name', 'source_type', 'title', 'country', 'keyword', 'published_at']], use_container_width=True)
