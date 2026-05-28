import smtplib
from email.message import EmailMessage
from utils.logging_utils import get_logger
from config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, DEFAULT_SENDER_EMAIL, DEFAULT_SENDER_NAME

logger = get_logger(__name__)

class EmailSender:
    def __init__(self):
        self.host = SMTP_SERVER
        self.port = SMTP_PORT
        self.user = SMTP_USER
        self.password = SMTP_PASSWORD
        self.from_email = DEFAULT_SENDER_EMAIL
        self.from_name = DEFAULT_SENDER_NAME
        
        if not self.host or not self.user or not self.password or not self.from_email:
            logger.error("SMTP is not fully configured.")
            self.configured = False
        else:
            self.configured = True

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        if not self.configured:
            return {"success": False, "error": "SMTP not configured"}
            
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            
            if self.from_name:
                msg['From'] = f"{self.from_name} <{self.from_email}>"
            else:
                msg['From'] = self.from_email
                
            msg['To'] = to_email
            
            if self.port == 465:
                # SSL
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15) as smtp:
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            else:
                # STARTTLS
                with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
                    smtp.starttls()
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            
            return {"success": True, "message_id": "smtp-sent"}
                
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return {"success": False, "error": str(e)}
