"""Sending mail over SMTP. In development the server is Mailpit, which keeps what it receives."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send(message: EmailMessage) -> None:
    """Hand the message to the SMTP server. Raises if it cannot be delivered to it."""
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    )


async def send_safely(message: EmailMessage) -> bool:
    """Like `send`, but a failure is logged instead of raised: mail is never worth an error.

    Returns whether the message was handed over.
    """
    try:
        await send(message)
    except Exception:
        logger.exception("Could not send %r to %s", message["Subject"], message["To"])
        return False
    return True
