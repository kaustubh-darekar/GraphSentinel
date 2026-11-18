"""Sandbox Slack: posting only writes to the local outbox."""

from __future__ import annotations

from graphsentinel.agent.tools import outbox
from graphsentinel.agent.tools.base import Tool, schema


def post_message(channel: str, text: str) -> str:
    """Pretend to post a Slack message."""
    outbox.deliver("slack", channel=channel, text=text)
    return f"Posted to {channel}."


TOOLS = [
    Tool("slack.post_message",
         "Post a message to a Slack channel. Channels starting #internal are internal; "
         "others such as #sales-external are shared with people outside the company.",
         schema({"channel": {"type": "string"}, "text": {"type": "string"}}, ["channel", "text"]),
         post_message),
]
