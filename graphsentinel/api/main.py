"""FastAPI app. Run with ONE worker and no --reload: Relate allows one writable process per store.

    uvicorn graphsentinel.api.main:app --workers 1
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from graphsentinel.api.events import EventBus
from graphsentinel.api.routes import router
from graphsentinel.api.runtime import Runtime
from graphsentinel.core.sentinel import Sentinel

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(sentinel: Sentinel | None = None) -> FastAPI:
    """Build the app. Tests pass their own (in-memory) Sentinel."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = sentinel is None
        if owned:  # tests pass their own Sentinel and must not pick up a developer's .env
            load_dotenv()
        s = sentinel or Sentinel.open()
        bus = EventBus()
        bus.bind(asyncio.get_running_loop())
        app.state.runtime = Runtime(s, bus)
        try:
            yield
        finally:
            if owned:
                s.close()

    app = FastAPI(title="GraphSentinel", lifespan=lifespan)
    app.include_router(router)
    if WEB_DIST.is_dir():  # `npm run build` output, served on the same port
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
