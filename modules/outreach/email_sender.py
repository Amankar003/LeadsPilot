import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class EmailSender:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL")
        if not self.api_key or not self.from_email:
            logger.error("SendGrid is not configured.")
            self.sg = None
        else:
            self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key)

    def send_email(self, to_email: str, subject: str, body: str) -> dict:
        if not self.sg:
            return {"success": False, "error": "SendGrid not configured"}
            
        try:
            from_email_obj = Email(self.from_email)
            to_email_obj = To(to_email)
            content = Content("text/plain", body)
            mail = Mail(from_email_obj, to_email_obj, subject, content)
            
            response = self.sg.client.mail.send.post(request_body=mail.get())
            
            if response.status_code in [200, 201, 202]:
                message_id = response.headers.get('X-Message-Id', 'unknown')
                return {"success": True, "message_id": message_id}
            else:
                return {"success": False, "error": f"Status: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return {"success": False, "error": str(e)}
