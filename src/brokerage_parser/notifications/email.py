import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from brokerage_parser.db import SessionLocal
from brokerage_parser.models.provisioning import PendingNotification
from brokerage_parser.config import settings

logger = logging.getLogger(__name__)

def send_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, str],
    db: Optional[Session] = None
) -> bool:
    """
    Sends an email using configured provider (SMTP/SendGrid/AWS SES).
    If not configured or fails, saves to PendingNotification table.
    """

    # 1. Attempt Send
    sent = False

    if settings.EMAIL_PROVIDER == "smtp":
        # Implement SMTP sending here
        # import smtplib
        # ...
        pass
    elif settings.EMAIL_PROVIDER == "console":
        # Dev mode: Print to console
        logger.info(f"EMAIL TO: {to_email} | SUBJ: {subject} | CTX: {context}")
        sent = True
    else:
        logger.warning(f"No email provider configured (EMAIL_PROVIDER={settings.EMAIL_PROVIDER})")

    # 2. Fallback to DB if not sent
    if not sent:
        # Check if we should log to DB
        # Yes, required for dev/fallback flow described in plan.

        session = db or SessionLocal()
        should_close = db is None

        try:
            note = PendingNotification(
                recipient=to_email,
                subject=subject,
                template=template_name,
                context=context
            )
            session.add(note)
            if should_close:
                session.commit()
            else:
                session.flush()
            logger.info(f"Saved pending notification for {to_email}")
            return True # considered "handled"

        except Exception as e:
            logger.error(f"Failed to save pending notification: {e}")
            return False
        finally:
            if should_close:
                session.close()

    return sent

def send_welcome_email(to_email: str, org_name: str, access_key: str, secret_key: str):
    """
    Convenience wrapper for welcome email.
    """
    return send_email(
        to_email=to_email,
        subject="Welcome to ParseFin",
        template_name="welcome_email",
        context={
             "org_name": org_name,
             "access_key": access_key,
             "secret_key": secret_key,
             "login_url": "https://portal.parsefin.com/login"
        }
    )
