import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///leadpilot.db")

# API Keys (Future use)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# SMTP Settings for Email Sender
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# App Constants
APP_NAME = "LeadPilot AI"
VERSION = "1.0.0"

# SendGrid Settings
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")

# Outreach Limits
DEFAULT_EMAIL_DELAY_SECONDS = int(os.getenv("DEFAULT_EMAIL_DELAY_SECONDS", 30))
MAX_EMAILS_PER_RUN = int(os.getenv("MAX_EMAILS_PER_RUN", 20))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", 2))

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
