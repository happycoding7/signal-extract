"""
Output delivery. CLI (stdout) and email.

CLI is the primary interface. Email is optional for scheduled runs.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

from config.settings import Config
from models import Digest, QAResult

log = logging.getLogger(__name__)


def deliver_cli(content: Digest | QAResult):
    """Print to stdout. That's it."""
    separator = "─" * 60

    if isinstance(content, Digest):
        type_headers = {
            "daily": "DAILY ENTERPRISE OPPORTUNITY SCAN",
            "weekly": "WEEKLY ENTERPRISE DEV-TOOL SYNTHESIS",
            "opportunities": "ENTERPRISE OPPORTUNITY REPORT",
        }
        header = type_headers.get(content.digest_type, content.digest_type.upper())
        print(f"\n{separator}")
        print(f"  {header}")
        print(f"  {content.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  ({content.item_count} items analyzed)")
        print(separator)
        print()
        print(content.content)
        print()
        print(separator)

    elif isinstance(content, QAResult):
        print(f"\n{separator}")
        print(f"  Q&A")
        print(separator)
        print(f"  Q: {content.question}")
        print(f"  ({content.sources_used} sources searched)")
        print(separator)
        print()
        print(content.answer)
        print()
        print(separator)


def deliver_email(content: Digest | QAResult, config: Config) -> bool:
    """Send via SMTP. Returns True on success."""
    if not config.smtp_host or not config.email_to:
        log.warning("Email not configured (SIGNAL_SMTP_HOST, SIGNAL_EMAIL_TO)")
        return False

    if isinstance(content, Digest):
        subject = f"[signal] {content.digest_type} — {content.generated_at.strftime('%Y-%m-%d')}"
        body = content.content
    elif isinstance(content, QAResult):
        subject = f"[signal] Q&A — {content.question[:50]}"
        body = f"Q: {content.question}\n\nA: {content.answer}"
    else:
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.email_from
    msg["To"] = config.email_to

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            if config.smtp_user:
                server.login(config.smtp_user, config.smtp_pass)
            server.send_message(msg)
        log.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        log.error(f"Email delivery failed: {e}")
        return False
