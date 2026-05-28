"""
modules/ui/mailforge/__init__.py — MailForge Bulk Email Engine entry point.
Renders a clean 3-tab interface: Campaign Sender, Sender Accounts, Settings.
"""
import streamlit as st

from modules.ui.mailforge.campaign_sender import render_campaign_sender
from modules.ui.mailforge.sender_accounts import render_sender_accounts
from modules.ui.mailforge.settings import render_settings


def render_mailforge():
    """
    Consolidated entry point for the MailForge Streamlit UI.
    MailForge is now a dedicated bulk email sending engine.
    Email generation and approval happen in Lead Intelligence Report Engine.
    """
    st.markdown("## 🔥 MailForge — Bulk Email Engine")
    st.caption(
        "Load approved emails from Lead Intelligence, configure senders, and send at scale."
    )

    tabs = st.tabs([
        "📤 Campaign Sender",
        "👤 Sender Accounts",
        "⚙️ Settings",
    ])

    with tabs[0]:
        render_campaign_sender()

    with tabs[1]:
        render_sender_accounts()

    with tabs[2]:
        render_settings()
