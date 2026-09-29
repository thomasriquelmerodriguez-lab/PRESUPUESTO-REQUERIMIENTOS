from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import DomainEvent
from app.services.auth import load_session

router = APIRouter(prefix="/events", tags=["events"])


def _fetch_events(last_id: int) -> list[DomainEvent]:
    with SessionLocal() as session:
        return list(
            session.execute(
                select(DomainEvent)
                .where(DomainEvent.id > last_id)
                .order_by(DomainEvent.id.asc())
                .limit(100)
            ).scalars()
        )


@router.get("")
async def event_stream(request: Request):
    with SessionLocal() as auth_db:
        _, user = load_session(auth_db, request)
    allowed = set(user["areas"])
    can_manage_users = "users.manage" in set(user.get("permissions", []))
    last_header = request.headers.get("last-event-id", "0")
    try:
        last_id = max(0, int(last_header))
    except ValueError:
        last_id = 0

    async def generate():
        nonlocal last_id
        heartbeat_at = time.monotonic()
        connected_at = time.monotonic()
        while not await request.is_disconnected() and time.monotonic() - connected_at < 300:
            rows = await asyncio.to_thread(_fetch_events, last_id)
            for row in rows:
                last_id = row.id
                if row.area_slug and row.area_slug not in allowed:
                    continue
                if row.event_type == "user.changed" and not can_manage_users:
                    continue
                payload = json.dumps(
                    {
                        "type": row.event_type,
                        "area": row.area_slug,
                        "payload": row.payload,
                        "created_at": row.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                )
                yield f"id: {row.id}\nevent: update\ndata: {payload}\n\n"
            if time.monotonic() - heartbeat_at > 20:
                heartbeat_at = time.monotonic()
                yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
