"""
MedScript Notification & Emergency Dispatch Service
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import get_config

config = get_config()


class NotificationService:
    def __init__(self):
        self.email_user = config.EMAIL_USER
        self.email_pass = config.EMAIL_PASSWORD or os.getenv("SENDER_EMAIL_PASSWORD", "")
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT

    def send_email(self, to_email, subject, body):
        """Send email notification via SMTP."""
        if not to_email or not self.email_pass:
            logging.info(f"Mock email delivery to {to_email} (no SMTP credentials): {subject}")
            return False

        sender = self.email_user or os.getenv("SENDER_EMAIL", "medscript-alerts@medscript.local")
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(sender, self.email_pass)
                server.sendmail(sender, to_email, msg.as_string())
            logging.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logging.error(f"Error sending email to {to_email}: {e}")
            return False

    def trigger_emergency_alert(self, user_name, user_phone, location, alert_type="SOS"):
        """Send emergency dispatch notification (Twilio SMS if configured, or email)."""
        subject = f"EMERGENCY HEALTH ALERT: {alert_type} from {user_name}"
        body = (
            f"URGENT HEALTH DISPATCH ALERT\n"
            f"User: {user_name}\n"
            f"Phone: {user_phone}\n"
            f"Location: {location}\n"
            f"Alert: {alert_type}\n"
            f"Timestamp: Sent via MedScript Emergency Services\n"
        )
        # 1. Try Twilio if credentials configured
        if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client
                client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=f"MEDSCRIPT SOS: {user_name} ({user_phone}) needs immediate assistance at {location}",
                    from_=config.TWILIO_FROM_NUMBER,
                    to=user_phone
                )
                logging.info(f"Twilio SOS message sent to {user_phone}")
                return True
            except Exception as e:
                logging.error(f"Twilio emergency dispatch failed: {e}")

        # 2. Fallback to configured emergency contact email
        return self.send_email(self.email_user, subject, body)


notification_service = NotificationService()
send_email = notification_service.send_email
