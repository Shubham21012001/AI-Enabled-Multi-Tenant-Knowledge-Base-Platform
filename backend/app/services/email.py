"""Email abstraction. Swap providers via EMAIL_PROVIDER without touching callers."""
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailProvider:
    """Development provider: logs that an email was sent.

    Links contain secret tokens, so the body is only printed outside production.
    """

    def send(self, to: str, subject: str, body: str) -> None:
        if settings.ENVIRONMENT == "production":
            logger.info("Email (console provider) to=%s subject=%r", to, subject)
        else:
            logger.info("Email to=%s subject=%r\n%s", to, subject, body)


class SmtpEmailProvider:
    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)


def get_email_provider() -> EmailProvider:
    return SmtpEmailProvider() if settings.EMAIL_PROVIDER == "smtp" else ConsoleEmailProvider()


def send_email(to: str, subject: str, body: str) -> None:
    """Never let an email failure break the request that triggered it."""
    try:
        get_email_provider().send(to, subject, body)
    except Exception:
        logger.exception("Failed to send email to=%s subject=%r", to, subject)
