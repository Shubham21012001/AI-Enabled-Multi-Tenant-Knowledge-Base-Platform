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


class ResendEmailProvider:
    def send(self, to: str, subject: str, body: str) -> None:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": settings.SMTP_FROM or "KnowBot <onboarding@resend.dev>",
            "to": to,
            "subject": subject,
            "text": body,
        })


def get_email_provider() -> EmailProvider:
    if settings.EMAIL_PROVIDER == "smtp":
        return SmtpEmailProvider()
    if settings.EMAIL_PROVIDER == "resend":
        return ResendEmailProvider()
    return ConsoleEmailProvider()


def send_email(to: str, subject: str, body: str) -> None:
    """Never let an email failure break the request that triggered it."""
    try:
        get_email_provider().send(to, subject, body)
        logger.info("Email to=%s subject=%r", to, subject)
    except Exception:
        logger.exception("Failed to send email to=%s subject=%r", to, subject)