"""
report_viewer_ui.py
View Intelligence Reports — Lead report viewer with interactive AI Outreach Generator.
"""
import streamlit as st
from datetime import datetime
from config.database import SessionLocal
from modules.database.models import Lead, AnalysisJob, AnalysisReport
from modules.analysis.job_processor import get_report
from modules.ui.theme import page_header, empty_state

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
EMAIL_TYPES = [
    "Cold Outreach",
    "Follow-up 1",
    "Follow-up 2",
    "No Website Pitch",
    "Website Redesign Pitch",
    "SEO Pitch",
    "App/Booking System Pitch",
    "AI Chatbot/Automation Pitch",
]

TONES = ["Professional", "Friendly", "Direct", "Consultative"]
LENGTHS = ["Short (80-100 words)", "Medium (100-140 words)"]
CTA_GOALS = ["Get Reply", "Book a Call", "Offer Free Audit", "Share Improvement Suggestions"]


# ─────────────────────────────────────────────
# Main Viewer
# ─────────────────────────────────────────────
def render_report_viewer():
    page_header(
        "📄",
        "View Intelligence Reports",
        "Review AI-generated sales reports and manage personalized outreach for each lead.",
    )

    db = SessionLocal()
    try:
        from modules.database.repositories import CampaignRepository
        campaigns = CampaignRepository(db).get_all()
        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="report_viewer_campaign",
        )

        leads = db.query(Lead).filter(Lead.campaign_id == selected_camp_id).all()
        if not leads:
            empty_state("👥", "No Leads", "No leads found for this campaign.")
            return

        jobs = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.lead_id.in_([l.id for l in leads]))
            .all()
        )
        job_map = {j.lead_id: j for j in jobs}
        analyzed_leads = [l for l in leads if job_map.get(l.id)]

        if not analyzed_leads:
            empty_state(
                "⏳",
                "No Analyzed Leads",
                "Go to '🧠 Lead Intelligence' to queue leads for analysis first.",
            )
            return

        lead_options = {
            l.id: f"{l.business_name}  [{job_map[l.id].status}]"
            for l in analyzed_leads
        }

        selected_lead_id = st.selectbox(
            "🔍 Select a lead to review:",
            options=list(lead_options.keys()),
            format_func=lambda x: lead_options[x],
        )

        if selected_lead_id:
            lead = db.query(Lead).filter(Lead.id == selected_lead_id).first()
            job = job_map.get(selected_lead_id)
            report = get_report(db, selected_lead_id)

            st.markdown(f"### 📄 Intelligence Dashboard — {lead.business_name}")

            if job.status == "PENDING":
                st.warning("⏳ Job is queued. Waiting for an open slot...")
            elif job.status == "RUNNING":
                st.info("⚙️ Analysis engine is currently auditing the website... (Takes 15-45s)")
                st.button("🔄 Refresh Status")
            elif job.status == "FAILED":
                st.error(f"❌ Analysis failed: {job.error_message}")
            elif job.status == "COMPLETED" and report:
                render_report_details(db, lead, report)
            elif job.status == "COMPLETED" and not report:
                st.error("⚠️ Job completed but report was not found in the database.")
                
    except Exception as e:
        db.rollback()
        st.error("⚠️ Database connection issue. Please refresh or try again.")
        st.exception(e)
    finally:
        db.close()


# ─────────────────────────────────────────────
# Report Details (Tabs)
# ─────────────────────────────────────────────
def render_report_details(db, lead: Lead, report: AnalysisReport):
    # Top metrics row
    c1, c2, c3 = st.columns(3)
    c1.metric("🏥 Digital Health Score", f"{report.overall_score}/100")
    c2.metric("🎯 Opportunity Score", f"{report.opportunity_score}/100")

    level = report.opportunity_level or "Unknown"
    color = (
        "green" if level in ["Very High", "High"]
        else "orange" if level == "Medium"
        else "gray"
    )
    c3.markdown(
        f"**Opportunity Level:**<br>"
        f"<span style='color:{color}; font-weight:bold; font-size:1.5rem;'>{level}</span>",
        unsafe_allow_html=True,
    )

    if not report.has_website:
        st.warning("⚠️ No website detected for this business. Pitch website development.")

    st.markdown("---")

    tabs = st.tabs([
        "📊 Executive Report",
        "💔 Pain Points & Services",
        "✉️ AI Outreach Generator",
        "📜 Outreach History",
        "🔍 Raw Audit Data",
    ])

    ai_data = report.ai_report_json or {}

    # ── Tab 0: Executive Report ──────────────────
    with tabs[0]:
        _render_executive_tab(ai_data)

    # ── Tab 1: Pain Points & Services ───────────
    with tabs[1]:
        _render_pain_points_tab(report)

    # ── Tab 2: Interactive Outreach Generator ────
    with tabs[2]:
        _render_outreach_tab(db, lead, report, ai_data)

    # ── Tab 3: Outreach History ──────────────────
    with tabs[3]:
        _render_history_tab(db, lead)

    # ── Tab 4: Raw Audit Data ────────────────────
    with tabs[4]:
        st.json(report.raw_audit_json or {})


# ─────────────────────────────────────────────
# Tab Renderers
# ─────────────────────────────────────────────
def _render_executive_tab(ai_data: dict):
    if not ai_data:
        st.info("Executive report is not yet available.")
        return

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("### 📋 Executive Summary")
        st.write(ai_data.get("executive_summary", "—"))

        st.markdown("### 💡 Business Impact")
        st.info(ai_data.get("business_impact_summary", "No impact summary available."))

        st.markdown("### 🗣️ Main Pitch Angle")
        st.success(f"**Pitch:** {ai_data.get('main_pitch_angle', '—')}")

    with col_b:
        st.markdown("### 📞 Sales Call Notes")
        notes = ai_data.get("sales_call_notes", [])
        if notes:
            for note in notes:
                st.markdown(f"✅ {note}")
        else:
            st.write("No specific notes generated.")

        tech = ai_data.get("technical_summary", {})
        if tech:
            st.markdown("### ⚙️ Technical TL;DR")
            for issue in tech.get("main_technical_issues", []):
                st.markdown(f"- {issue}")


def _render_pain_points_tab(report: AnalysisReport):
    st.markdown("### 🔴 Detected Pain Points")
    pps = report.pain_points_json or []
    if not pps:
        st.info("No pain points were detected for this lead.")
    else:
        for pp in pps:
            sev = str(pp.get("severity", "")).capitalize()
            icon = "🔴" if sev == "Critical" else "🟠" if sev == "High" else "🟡"
            with st.expander(
                f"{icon} {pp.get('title')} ({sev})",
                expanded=(sev in ["Critical", "High"]),
            ):
                st.write(f"**Evidence:** {pp.get('evidence', '—')}")
                st.write(f"**Business Impact:** {pp.get('business_impact', '—')}")
                rec = pp.get("recommended_service")
                if rec:
                    st.caption(f"💡 Recommended Service: {rec}")

    st.markdown("---")
    st.markdown("### ✅ Recommended Solutions")
    recs = report.recommended_services_json or []
    if not recs:
        st.info("No specific services recommended.")
    else:
        for rec in recs:
            pri = rec.get("priority", "")
            pri_color = (
                "🔴" if pri == "High" else "🟠" if pri == "Medium" else "🟢"
            )
            st.markdown(f"#### {pri_color} {rec.get('service_name')} — Priority: {pri}")
            st.markdown(f"**Why they need it:** {rec.get('reason', '—')}")
            st.markdown(f"**How to pitch it:** {rec.get('pitch_angle', '—')}")
            st.divider()


def _render_outreach_tab(db, lead: Lead, report: AnalysisReport, ai_data: dict):
    st.markdown("### ✉️ AI Outreach Generator")

    # 5. Show warning if report or ai_report_json is missing
    if not report or not report.ai_report_json:
        st.warning("⚠️ Analysis report is missing. Please run Lead Intelligence Analysis first.")
        return

    from modules.database.repositories import OutreachMessageRepository
    from modules.database.models import MailForgeCampaign, MailForgeDraft
    from modules.analysis.outreach_generator import generate_outreach

    # Load latest outreach from DB if present
    repo = OutreachMessageRepository(db)
    latest = repo.get_latest_for_lead(lead.id)

    # 6. Detect weak legacy emails under 80 words and automatically regenerate
    if latest and latest.email_body:
        core_body = latest.email_body
        if "\n\nBest regards," in core_body:
            core_body = core_body.split("\n\nBest regards,")[0]
        word_count = len(core_body.strip().split())
        if word_count < 80:
            import logging
            logger = logging.getLogger("leadpilot")
            logger.info(f"Loaded outreach message is weak ({word_count} words). Forcing automatic regeneration.")
            latest = None

    # ── Automatic Generation if not present ───────
    if not latest:
        with st.spinner("🤖 Automatically generating outreach based on the report..."):
            try:
                result = generate_outreach(
                    report=report,
                    lead=lead,
                    email_type="Cold Outreach",
                    tone="Professional",
                    length="Short",
                    cta_goal="Get Reply",
                    service_focus="Auto (from report)",
                )

                if "error" not in result:
                    # Automatically save to OutreachMessageRepository
                    latest = repo.create(
                        lead_id=lead.id,
                        report_id=report.id,
                        email_type="Cold Outreach",
                        tone="Professional",
                        length="Short",
                        cta_goal="Get Reply",
                        service_focus="Auto (from report)",
                        subject_lines=result.get("subject_lines", []),
                        email_body=result.get("email_body", ""),
                        whatsapp_message=result.get("whatsapp_message", ""),
                        linkedin_message=result.get("linkedin_message", ""),
                        follow_up_1=result.get("follow_up_1", ""),
                        follow_up_2=result.get("follow_up_2", ""),
                    )

                    # Save into MailForge drafts
                    mf_campaign = db.query(MailForgeCampaign).filter(
                        MailForgeCampaign.campaign_id == lead.campaign_id
                    ).first()
                    if not mf_campaign:
                        mf_campaign = MailForgeCampaign(
                            name=f"MailForge {lead.campaign_id[:8]}",
                            campaign_id=lead.campaign_id,
                            description="Auto-created from Intelligence report viewer",
                            tone="professional",
                            email_length="medium",
                            status="active",
                        )
                        db.add(mf_campaign)
                        db.flush()
                    existing_draft = db.query(MailForgeDraft).filter(
                        MailForgeDraft.lead_id == lead.id,
                        MailForgeDraft.mailforge_campaign_id == mf_campaign.id,
                    ).first()
                    if not existing_draft:
                        db.add(MailForgeDraft(
                            lead_id=lead.id,
                            mailforge_campaign_id=mf_campaign.id,
                            subject=result.get("subject_lines", ["Ideas for " + lead.business_name])[0],
                            body=result.get("email_body", ""),
                            opening_line=result.get("preview_text", ai_data.get("main_pitch_angle", "")),
                            personalization_reason=result.get("personalization_used", "Website Audit + AI"),
                            confidence_score=str(result.get("confidence_score", "0.7")),
                            status="draft",
                        ))
                        db.commit()
                    st.success("✅ Outreach generated and saved automatically!")
                    st.rerun()
                else:
                    st.error(f"❌ Auto-generation failed: {result['error']}")
                    return
            except Exception as e:
                st.error(f"❌ Auto-generation failed: {e}")
                return

    # Once loaded or automatically generated, we put it in st.session_state
    result = st.session_state.get(f"outreach_result_{lead.id}")
    if not result:
        result = {
            "subject_lines": latest.subject_lines or [],
            "email_body": latest.email_body or "",
            "whatsapp_message": latest.whatsapp_message or "",
            "linkedin_message": latest.linkedin_message or "",
            "follow_up_1": latest.follow_up_1 or "",
            "follow_up_2": latest.follow_up_2 or "",
            "_db_id": latest.id,
        }
        st.session_state[f"outreach_result_{lead.id}"] = result

    if not result:
        st.info("No outreach messages available.")
        return

    st.markdown("---")

    # ── Email Section ────────────────────────────
    st.markdown("#### 📧 Email Draft")

    subjects = result.get("subject_lines", [])
    if subjects:
        selected_subject = st.selectbox(
            "📌 Select Subject Line",
            subjects,
            key=f"subj_{lead.id}",
        )
    else:
        selected_subject = st.text_input("📌 Subject Line", value="", key=f"subj_{lead.id}")

    edited_body = st.text_area(
        "Email Body",
        value=result.get("email_body", ""),
        height=220,
        key=f"body_{lead.id}",
        label_visibility="collapsed",
    )

    # ── Quick-Edit Buttons ───────────────────────
    st.markdown("**✏️ Quick Edits:**")
    qe1, qe2, qe3, qe4 = st.columns(4)

    def _apply_modifier_action(modifier_key: str):
        from modules.analysis.outreach_generator import apply_modifier
        with st.spinner("Applying edit..."):
            new_body = apply_modifier(edited_body, modifier_key)
        result["email_body"] = new_body
        st.session_state[f"outreach_result_{lead.id}"] = result
        st.rerun()

    with qe1:
        if st.button("✂️ Make Shorter", use_container_width=True, key=f"short_{lead.id}"):
            _apply_modifier_action("make_shorter")
    with qe2:
        if st.button("🎩 More Professional", use_container_width=True, key=f"prof_{lead.id}"):
            _apply_modifier_action("make_professional")
    with qe3:
        if st.button("😊 More Friendly", use_container_width=True, key=f"friend_{lead.id}"):
            _apply_modifier_action("make_friendly")
    with qe4:
        if st.button("💪 Stronger CTA", use_container_width=True, key=f"cta_btn_{lead.id}"):
            _apply_modifier_action("stronger_cta")

    # ── Regenerate & Approve Row ─────────────────
    st.markdown("")
    btn_reg, btn_approve = st.columns([1, 1])

    with btn_reg:
        if st.button("🔄 Regenerate Email", use_container_width=True, key=f"regen_{lead.id}"):
            from modules.analysis.outreach_generator import generate_outreach
            from modules.database.repositories import OutreachMessageRepository
            from modules.database.models import MailForgeCampaign, MailForgeDraft
            with st.spinner("Regenerating..."):
                new_result = generate_outreach(
                    report=report,
                    lead=lead,
                    email_type=st.session_state.get(f"et_{lead.id}", "Cold Outreach"),
                    tone=st.session_state.get(f"tone_{lead.id}", "Professional"),
                    length=st.session_state.get(f"len_{lead.id}", "Short").split(" ")[0],
                    cta_goal=st.session_state.get(f"cta_{lead.id}", "Get Reply"),
                    service_focus=st.session_state.get(f"svc_{lead.id}", "Auto (from report)"),
                )
            if "error" not in new_result:
                # Save immediately to DB to overwrite cached legacy emails
                outreach_repo = OutreachMessageRepository(db)
                new_msg = outreach_repo.create(
                    lead_id=lead.id,
                    report_id=report.id,
                    email_type=st.session_state.get(f"et_{lead.id}", "Cold Outreach"),
                    tone=st.session_state.get(f"tone_{lead.id}", "Professional"),
                    length=st.session_state.get(f"len_{lead.id}", "Short").split(" ")[0],
                    cta_goal=st.session_state.get(f"cta_{lead.id}", "Get Reply"),
                    service_focus=st.session_state.get(f"svc_{lead.id}", "Auto (from report)"),
                    subject_lines=new_result.get("subject_lines", []),
                    email_body=new_result.get("email_body", ""),
                    whatsapp_message=new_result.get("whatsapp_message", ""),
                    linkedin_message=new_result.get("linkedin_message", ""),
                    follow_up_1=new_result.get("follow_up_1", ""),
                    follow_up_2=new_result.get("follow_up_2", ""),
                )
                new_result["_db_id"] = new_msg.id
                
                mf_campaign = db.query(MailForgeCampaign).filter(
                    MailForgeCampaign.campaign_id == lead.campaign_id
                ).first()
                if not mf_campaign:
                    mf_campaign = MailForgeCampaign(
                        name=f"MailForge {lead.campaign_id[:8]}",
                        campaign_id=lead.campaign_id,
                        description="Auto-created from Intelligence report viewer",
                        tone="professional",
                        email_length="medium",
                        status="active",
                    )
                    db.add(mf_campaign)
                    db.flush()
                existing_draft = db.query(MailForgeDraft).filter(
                    MailForgeDraft.lead_id == lead.id,
                    MailForgeDraft.mailforge_campaign_id == mf_campaign.id,
                ).first()
                if existing_draft:
                    existing_draft.subject = new_result.get("subject_lines", ["Ideas"])[0]
                    existing_draft.body = new_result.get("email_body", "")
                    existing_draft.status = "edited"
                else:
                    db.add(MailForgeDraft(
                        lead_id=lead.id,
                        mailforge_campaign_id=mf_campaign.id,
                        subject=new_result.get("subject_lines", ["Ideas"])[0],
                        body=new_result.get("email_body", ""),
                        opening_line=new_result.get("preview_text", ""),
                        personalization_reason=new_result.get("personalization_used", "Website Audit + AI"),
                        confidence_score=str(new_result.get("confidence_score", "0.7")),
                        status="draft",
                    ))
                db.commit()
                
                st.session_state[f"outreach_result_{lead.id}"] = new_result
                st.success("✅ Email regenerated and saved to database successfully!")
                st.rerun()
            else:
                st.error(new_result.get("error"))

    with btn_approve:
        if st.button(
            "✅ Approve & Save to CRM",
            type="primary",
            use_container_width=True,
            key=f"approve_{lead.id}",
        ):
            from modules.database.repositories import OutreachMessageRepository, LeadRepository
            from modules.database.models import MailForgeCampaign, MailForgeDraft
            try:
                mf_campaign = db.query(MailForgeCampaign).filter(
                    MailForgeCampaign.campaign_id == lead.campaign_id
                ).first()
                if not mf_campaign:
                    mf_campaign = MailForgeCampaign(
                        name=f"MailForge {lead.campaign_id[:8]}",
                        campaign_id=lead.campaign_id,
                        description="Auto-created from Intelligence report viewer",
                        tone="professional",
                        email_length="medium",
                        status="active",
                    )
                    db.add(mf_campaign)
                    db.flush()
                existing = db.query(MailForgeDraft).filter(
                    MailForgeDraft.lead_id == lead.id,
                    MailForgeDraft.mailforge_campaign_id == mf_campaign.id,
                ).first()
                if not existing:
                    db.add(MailForgeDraft(
                        lead_id=lead.id,
                        mailforge_campaign_id=mf_campaign.id,
                        subject=selected_subject,
                        body=edited_body,
                        opening_line=result.get("preview_text", ai_data.get("main_pitch_angle", "")),
                        personalization_reason=result.get("personalization_used", "Website Audit + AI"),
                        confidence_score=str(result.get("confidence_score", "0.7")),
                        status="approved",
                    ))
                else:
                    existing.subject = selected_subject
                    existing.body = edited_body
                    existing.status = "approved"
                db.commit()

                # Mark outreach as approved
                db_id = result.get("_db_id")
                if db_id:
                    OutreachMessageRepository(db).approve(db_id, selected_subject)

                # Update lead status
                LeadRepository(db).update_status(lead.id, "EMAIL_GENERATED")
                st.success("✅ Email approved and saved to MailForge Drafts!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save: {e}")

    st.markdown("---")

    # ── Social & Messaging ───────────────────────
    st.markdown("#### 💬 Social & Messaging Variants")

    wa_col, li_col = st.columns(2)
    with wa_col:
        st.markdown("**📱 WhatsApp Message**")
        wa_val = st.text_area(
            "WhatsApp",
            value=result.get("whatsapp_message", ""),
            height=140,
            key=f"wa_{lead.id}",
            label_visibility="collapsed",
        )
        wa_btn1, wa_btn2 = st.columns(2)
        with wa_btn1:
            if st.button("🔄 Regenerate", key=f"regen_wa_{lead.id}", use_container_width=True):
                from modules.analysis.outreach_generator import generate_single_channel
                new_wa = generate_single_channel("whatsapp", result, lead, report)
                result["whatsapp_message"] = new_wa
                st.session_state[f"outreach_result_{lead.id}"] = result
                st.rerun()
        with wa_btn2:
            st.caption("Copy & paste to WhatsApp Web")

    with li_col:
        st.markdown("**💼 LinkedIn Message**")
        li_val = st.text_area(
            "LinkedIn",
            value=result.get("linkedin_message", ""),
            height=140,
            key=f"li_{lead.id}",
            label_visibility="collapsed",
        )
        li_btn1, li_btn2 = st.columns(2)
        with li_btn1:
            if st.button("🔄 Regenerate", key=f"regen_li_{lead.id}", use_container_width=True):
                from modules.analysis.outreach_generator import generate_single_channel
                new_li = generate_single_channel("linkedin", result, lead, report)
                result["linkedin_message"] = new_li
                st.session_state[f"outreach_result_{lead.id}"] = result
                st.rerun()
        with li_btn2:
            st.caption("Copy & paste to LinkedIn")

    st.markdown("---")

    # ── Follow-up Sequences ──────────────────────
    st.markdown("#### 🔁 Follow-up Sequence")
    fu1, fu2 = st.columns(2)
    with fu1:
        st.markdown("**Follow-up #1**")
        st.text_area(
            "Follow-up 1",
            value=result.get("follow_up_1", ""),
            height=160,
            key=f"fu1_{lead.id}",
            label_visibility="collapsed",
        )
    with fu2:
        st.markdown("**Follow-up #2**")
        st.text_area(
            "Follow-up 2",
            value=result.get("follow_up_2", ""),
            height=160,
            key=f"fu2_{lead.id}",
            label_visibility="collapsed",
        )


def _render_history_tab(db, lead: Lead):
    st.markdown("### 📜 Outreach Generation History")
    st.caption("All previously generated outreach variations for this lead.")

    from modules.database.repositories import OutreachMessageRepository
    history = OutreachMessageRepository(db).get_by_lead_id(lead.id)

    if not history:
        st.info("No outreach has been generated yet for this lead.")
        return

    for i, msg in enumerate(history):
        approved_badge = " ✅ **APPROVED**" if msg.is_approved else ""
        label = (
            f"#{i+1} · {msg.email_type} · {msg.tone} · {msg.created_at.strftime('%d %b %Y %H:%M')}"
            f"{approved_badge}"
        )
        with st.expander(label, expanded=(i == 0)):
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.markdown(f"**Type:** {msg.email_type}")
                st.markdown(f"**Tone:** {msg.tone} | **Length:** {msg.length} | **CTA:** {msg.cta_goal}")
                st.markdown(f"**Service Focus:** {msg.service_focus}")
            with col_b:
                if msg.is_approved:
                    st.success(f"Approved Subject: {msg.approved_subject}")
                    st.caption(f"Approved at: {msg.approved_at}")

            st.markdown("**Subject Lines:**")
            for subj in (msg.subject_lines or []):
                st.markdown(f"- {subj}")

            st.markdown("**Email Body:**")
            st.code(msg.email_body or "—", language=None)

            if msg.whatsapp_message:
                st.markdown("**WhatsApp:**")
                st.code(msg.whatsapp_message, language=None)

            if msg.linkedin_message:
                st.markdown("**LinkedIn:**")
                st.code(msg.linkedin_message, language=None)

            # Load into active session
            if st.button(f"📥 Load This Version", key=f"load_{msg.id}"):
                st.session_state[f"outreach_result_{lead.id}"] = {
                    "subject_lines": msg.subject_lines or [],
                    "email_body": msg.email_body or "",
                    "whatsapp_message": msg.whatsapp_message or "",
                    "linkedin_message": msg.linkedin_message or "",
                    "follow_up_1": msg.follow_up_1 or "",
                    "follow_up_2": msg.follow_up_2 or "",
                    "_db_id": msg.id,
                }
                st.rerun()
