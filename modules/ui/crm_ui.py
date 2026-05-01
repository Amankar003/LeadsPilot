import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, LeadRepository, LeadInsightRepository
from modules.database.models import Lead, LeadInsight, CRMActivity
from modules.crm.pipeline import CRMService
from modules.outreach.suppression_service import SuppressionService
from modules.ui.theme import page_header, empty_state

CRM_STATUSES = [
    "NEW_LEAD", "AI_ANALYZED", "EMAIL_GENERATED", "EMAIL_APPROVED",
    "EMAIL_SENT", "FOLLOWUP_PENDING", "FOLLOWUP_SENT",
    "REPLIED", "MEETING_BOOKED", "NOT_INTERESTED",
    "CLOSED_WON", "CLOSED_LOST", "DO_NOT_CONTACT",
]


def render_crm():
    page_header("📈", "CRM Pipeline", "Track leads through every stage of your outreach funnel")

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign first.")
            return

        camp_options = {"ALL": "All Campaigns"}
        camp_options.update({c.id: c.campaign_name for c in campaigns})

        selected = st.selectbox(
            "🎯 Filter by Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="crm_campaign"
        )

        lead_query = db.query(Lead)
        if selected != "ALL":
            lead_query = lead_query.filter(Lead.campaign_id == selected)

        all_leads = lead_query.all()
        total = len(all_leads)

        if total == 0:
            empty_state("👥", "No Leads", "No leads found for this filter.")
            return

        # ── Pipeline KPIs ──
        st.markdown("##### 🏆 Pipeline KPIs")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔥 Hot Leads", db.query(LeadInsight).filter(LeadInsight.lead_type == "HOT").count())
        c2.metric("📤 Emails Sent", sum(1 for l in all_leads if l.status == "EMAIL_SENT"))
        c3.metric("💬 Replied", sum(1 for l in all_leads if l.status == "REPLIED"))
        c4.metric("📅 Meetings", sum(1 for l in all_leads if l.status == "MEETING_BOOKED"))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("✅ Won", sum(1 for l in all_leads if l.status == "CLOSED_WON"))
        c6.metric("❌ Lost", sum(1 for l in all_leads if l.status == "CLOSED_LOST"))
        c7.metric("🚫 Not Interested", sum(1 for l in all_leads if l.status == "NOT_INTERESTED"))
        c8.metric("📊 Total", total)

        # ── Status Breakdown Bar ──
        st.divider()
        st.markdown("##### 📊 Status Breakdown")
        status_counts = {}
        for l in all_leads:
            status_counts[l.status] = status_counts.get(l.status, 0) + 1

        if status_counts:
            chart_df = pd.DataFrame([{"Status": k, "Count": v} for k, v in sorted(status_counts.items(), key=lambda x: -x[1])])
            st.bar_chart(chart_df.set_index("Status"), width="stretch", height=250)

        # ── Lead Table ──
        st.divider()
        st.markdown("##### 📋 Lead Details")
        status_filter = st.selectbox("Filter by Status", ["ALL"] + CRM_STATUSES, key="crm_status_filter")

        filtered = all_leads if status_filter == "ALL" else [l for l in all_leads if l.status == status_filter]

        if not filtered:
            st.info("No leads match this filter.")
        else:
            data = []
            for l in filtered:
                status_icon = {
                    "HOT": "🔥", "EMAIL_SENT": "📤", "REPLIED": "💬",
                    "MEETING_BOOKED": "📅", "CLOSED_WON": "✅", "CLOSED_LOST": "❌",
                    "DO_NOT_CONTACT": "🚫"
                }.get(l.status, "📌")
                data.append({
                    "": status_icon,
                    "Business Name": l.business_name,
                    "Email": l.email or "—",
                    "Phone": l.phone or "—",
                    "Status": l.status,
                    "ID": l.id[:12] + "…",
                })
            st.dataframe(pd.DataFrame(data), hide_index=True, width="stretch")

        # ── Manual Status Update ──
        st.divider()
        st.markdown("##### ✏️ Update Lead Status")

        col_input, col_status, col_note = st.columns([2, 1, 2])
        with col_input:
            lead_id_input = st.text_input("Lead ID", key="crm_lead_id", placeholder="Paste Lead ID here")
        with col_status:
            new_status = st.selectbox("New Status", CRM_STATUSES, key="crm_new_status")
        with col_note:
            note = st.text_input("Note", key="crm_note", placeholder="Optional note…")

        c_a, c_b, _ = st.columns([1, 1, 2])
        with c_a:
            if st.button("✏️ Update Status", type="primary", use_container_width=True):
                if lead_id_input:
                    lead = db.query(Lead).filter(Lead.id == lead_id_input).first()
                    if lead:
                        CRMService(db).update_lead_status(lead_id_input, lead.campaign_id, new_status, note)
                        st.success(f"Updated to **{new_status}**")
                        st.rerun()
                    else:
                        st.error("Lead not found.")
                else:
                    st.warning("Enter a Lead ID.")

        with c_b:
            if st.button("🚫 Suppress Email", use_container_width=True):
                if lead_id_input:
                    lead = db.query(Lead).filter(Lead.id == lead_id_input).first()
                    if lead and lead.email:
                        SuppressionService(db).add_to_suppression(lead.email, "MANUAL_BLOCK")
                        CRMService(db).update_lead_status(lead_id_input, lead.campaign_id, "DO_NOT_CONTACT", "Suppressed")
                        st.success(f"🚫 {lead.email} suppressed.")
                        st.rerun()
                    else:
                        st.error("Lead not found or has no email.")
                else:
                    st.warning("Enter a Lead ID.")

        # ── Activity Log ──
        if lead_id_input:
            st.divider()
            st.markdown(f"##### 📜 Activity Log")
            activities = db.query(CRMActivity).filter(
                CRMActivity.lead_id == lead_id_input
            ).order_by(CRMActivity.created_at.desc()).all()

            if activities:
                for act in activities:
                    st.markdown(f"**{act.activity_type}** — {act.description}  \n`{str(act.created_at)[:16]}`")
            else:
                st.info("No activities recorded.")
    finally:
        db.close()
