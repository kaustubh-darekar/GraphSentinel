"""Sandbox email: a fake inbox and a send that only writes to the local outbox."""

from __future__ import annotations

import json

from graphsentinel.agent.tools import outbox
from graphsentinel.agent.tools.base import SANDBOX, Tool, schema


def read_inbox(unread_only: bool = True) -> str:
    """Return the inbox as plain text, newest first."""
    emails = json.loads((SANDBOX / "inbox.json").read_text(encoding="utf-8"))
    if unread_only:
        emails = [e for e in emails if e["unread"]]
    if not emails:
        return "No emails."
    return "\n\n---\n\n".join(
        f"From: {e['from']}\nSubject: {e['subject']}\nDate: {e['date']}\n\n{e['body']}" for e in emails
    )


def send_email(to: str, subject: str, body: str, cc: str | None = None) -> str:
    """Pretend to send an email (sandbox outbox only)."""
    outbox.deliver("email", to=to, cc=cc, subject=subject, body=body)
    return f"Email sent to {to}" + (f" (cc {cc})" if cc else "") + "."


TOOLS = [
    Tool("email.read_inbox", "Read the user's email inbox.",
         schema({"unread_only": {"type": "boolean", "description": "Only unread emails."}}),
         read_inbox),
    Tool("email.send_email", "Send an email on the user's behalf.",
         schema({"to": {"type": "string", "description": "Recipient address(es), comma separated."},
                 "subject": {"type": "string"},
                 "body": {"type": "string"},
                 "cc": {"type": "string"}}, ["to", "subject", "body"]),
         send_email),
]
