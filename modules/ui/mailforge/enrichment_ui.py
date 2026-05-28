import streamlit as st
import pandas as pd
from modules.mailforge.enrichment import MailForgeEnricher
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeLead

def render_enrichment():
    st.markdown("### 🌐 Email-Only Lead Enrichment")
    st.caption("Performs automatic business website inference and metadata extraction (socials, phone, business name) for corporate domains. Flag free domains for manual review.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a MailForge campaign first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Select Campaign to Enrich",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="enrich_select_camp"
        )

        leads = db.query(MailForgeLead).filter(
            MailForgeLead.mailforge_campaign_id == selected_campaign_id
        ).all()

        if not leads:
            st.info("No leads imported into this campaign yet. Upload some leads first!")
            return

        # Summary of current lead statuses
        status_counts = {}
        for l in leads:
            status_counts[l.enrichment_status] = status_counts.get(l.enrichment_status, 0) + 1

        st.markdown("#### 📊 Campaign Leads Status")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pending", status_counts.get("PENDING", 0))
        c2.metric("Enriched", status_counts.get("enriched", 0))
        c3.metric("Needs Review (Free)", status_counts.get("needs_review", 0))
        c4.metric("Partial/Failed", status_counts.get("partial", 0) + status_counts.get("failed", 0))

        st.divider()

        # Run Enrichment
        pending_leads = [l for l in leads if l.enrichment_status == "PENDING"]
        if not pending_leads:
            st.success("🎉 All leads in this campaign have been processed!")
        else:
            if st.button("🚀 Start Lead Enrichment Job", type="primary", use_container_width=True):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                enricher = MailForgeEnricher()
                
                success_count = 0
                for idx, lead in enumerate(pending_leads):
                    status_text.text(f"Enriching {lead.email}... ({idx+1}/{len(pending_leads)})")
                    progress_bar.progress((idx + 1) / len(pending_leads))
                    
                    try:
                        # Enrich
                        data = enricher.enrich_email(lead.email)
                        
                        # Update lead record
                        lead.domain = data["domain"]
                        lead.website = data["website"]
                        lead.business_name = data["business_name"] or lead.business_name
                        lead.enrichment_status = data["enrichment_status"]
                        
                        import json
                        lead.confidence_score = json.dumps({
                            "score": data["confidence_score"],
                            "phone": data["phone"],
                            "socials": data["social_links"],
                            "notes": data["notes"]
                        })
                        success_count += 1
                    except Exception as e:
                        lead.enrichment_status = "failed"
                        lead.confidence_score = json.dumps({"score": 0.0, "error": str(e)})

                    # Commit every 5 records to prevent connection timeout
                    if idx % 5 == 0:
                        db.commit()

                db.commit()
                st.success(f"🎉 Enrichment job complete! Processed **{success_count}** leads successfully.")
                st.rerun()

        # Show detailed leads table
        st.divider()
        st.markdown("#### 👥 Enriched Leads Details")
        
        lead_data = []
        for l in leads:
            # Parse extra fields
            phone = ""
            notes = ""
            if l.confidence_score:
                try:
                    import json
                    meta = json.loads(l.confidence_score) if isinstance(l.confidence_score, str) else l.confidence_score
                    phone = meta.get("phone", "")
                    notes = meta.get("notes", "")
                except:
                    pass

            lead_data.append({
                "Email": l.email,
                "Business Name": l.business_name or "N/A",
                "Website": l.website or "N/A",
                "Enrichment Status": l.enrichment_status,
                "Phone": phone,
                "Notes": notes
            })
        
        st.dataframe(pd.DataFrame(lead_data), hide_index=True, use_container_width=True)

    finally:
        db.close()
