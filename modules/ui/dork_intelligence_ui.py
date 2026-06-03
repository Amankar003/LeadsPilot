import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.dork_optimizer.service import DorkOptimizerService
from modules.dork_optimizer.db_adapter import (
    get_today_source_data,
    get_today_recommendations,
    get_pipeline_status,
    get_source_summary
)
from modules.dork_optimizer.services.pipeline import run_pipeline
from modules.ui.components.opportunity_card import render_opportunity_card
from modules.ui.components.dork_list import render_dork_list
from modules.ui.components.campaign_selector import render_campaign_selector

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

    st.markdown("---")
    st.markdown("### 🎯 High-Value Intelligence Opportunities")
    
    recs = get_today_recommendations()
    if not recs:
        st.info("No recommendations generated today. Run the pipeline above to gather intelligence.")
    else:
        db = SessionLocal()
        try:
            service = DorkOptimizerService(db)
            
            for idx, r in enumerate(recs):
                with st.container(border=True):
                    # 1. Opportunity Context
                    opp_data = {
                        "category": r.get("trend_name", "Unknown Trend"),
                        "region": r.get("region"),
                        "country": r.get("country"),
                        "trend_summary": f"Signal identified for {r.get('sector', 'various')} sector.",
                        "opportunity_reason": "High demand indicated by local market shifts.",
                        "target_service": r.get("recommended_service", "Any"),
                        "score": r.get("opportunity_score", 50)
                    }
                    render_opportunity_card(opp_data)
                    
                    # 2. Generated Dorks & Copy Controls
                    dorks = r.get('dorks', [])
                    selected_dork_ids = render_dork_list(dorks, opp_id=f"intel_{r.get('id', idx)}")
                    
                    # 3. Campaign Selection & Actions
                    st.markdown("---")
                    render_campaign_selector(db, service, selected_dork_ids, opp_id=f"intel_{r.get('id', idx)}")
                    
        except Exception as e:
            st.error(f"Error rendering intelligence dashboard: {e}")
        finally:
            db.close()

    st.markdown("---")
    with st.expander("🌐 View Raw Aggregated Sources"):
        summary = get_source_summary()
        st.write(f"**Total Today:** {summary['total_today']}")
        st.write(f"**By Source:** {summary['by_source']}")
        
        sources = get_today_source_data()
        if not sources:
            st.info("No source data fetched today.")
        else:
            df_src = pd.DataFrame(sources)
            st.dataframe(df_src[['source_name', 'source_type', 'title', 'country', 'keyword', 'published_at']], use_container_width=True)
