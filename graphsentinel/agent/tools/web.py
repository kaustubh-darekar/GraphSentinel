"""Sandbox web: fetches only the fake pages in sandbox_data/web/pages.json."""

from __future__ import annotations

import json

from graphsentinel.agent.tools.base import SANDBOX, Tool, schema


def fetch_url(url: str) -> str:
    """Text of a sandbox web page."""
    pages = json.loads((SANDBOX / "web" / "pages.json").read_text(encoding="utf-8"))
    page = pages.get(url.strip())
    if page is None:
        return f"Error: 404, {url} is not in the sandbox. Known pages: " + ", ".join(pages)
    return f"{page['title']}\n\n{page['body']}"


TOOLS = [
    Tool("web.fetch_url", "Fetch a web page and return its text.",
         schema({"url": {"type": "string"}}, ["url"]), fetch_url),
]
