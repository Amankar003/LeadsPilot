import os
import requests
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def get_base_url():
    return os.getenv("MAILFORGE_API_URL", "http://localhost:5000").rstrip("/")

def check_mailforge_health():
    try:
        res = requests.get(f"{get_base_url()}/health", timeout=5)
        if res.status_code == 200:
            return True, res.json().get("service", "Unknown")
        return False, "Bad status"
    except Exception as e:
        logger.error(f"MailForge health check failed: {e}")
        return False, str(e)

def test_sender_via_mailforge_api(sender_account_id: str):
    try:
        res = requests.post(
            f"{get_base_url()}/api/mailforge/test-sender",
            json={"sender_account_id": sender_account_id},
            timeout=10
        )
        return res.json()
    except Exception as e:
        logger.error(f"MailForge test-sender failed: {e}")
        return {"ok": False, "error": str(e)}

def send_draft_via_mailforge_api(campaign_id: str, draft_id: str):
    try:
        res = requests.post(
            f"{get_base_url()}/api/mailforge/send-draft",
            json={"campaign_id": campaign_id, "draft_id": draft_id},
            timeout=30
        )
        return res.json()
    except Exception as e:
        logger.error(f"MailForge send-draft failed: {e}")
        return {"ok": False, "error": str(e)}

def send_bulk_via_mailforge_api(campaign_id: str, draft_ids: list[str]):
    try:
        res = requests.post(
            f"{get_base_url()}/api/mailforge/send-bulk",
            json={"campaign_id": campaign_id, "draft_ids": draft_ids},
            timeout=60 * 5  # Give it ample time for bulk operations
        )
        return res.json()
    except Exception as e:
        logger.error(f"MailForge send-bulk failed: {e}")
        return {"ok": False, "error": str(e)}
