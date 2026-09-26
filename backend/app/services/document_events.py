"""Live updates for the Documents page.

Every open Documents page holds a WebSocket, grouped by the doctor profile it
belongs to (a doctor and all of their staff share one group). Any doctor-side
change -- creating, editing or deleting a document, uploading or removing a
file, sharing/fill-link toggles, adding a patient -- or a patient's own
change through their fill-in link, calls emit_event() here, and every open
page for that doctor refetches right away instead of waiting for its next
poll.

Unlike the earlier version of this module, the notification isn't delivered
by calling the in-process WebSocket manager directly. It's sent through
Postgres itself, with `pg_notify()` / `LISTEN` (see PostgresEventBridge
below): every mutation issues a NOTIFY on the `documents_changes` channel as
part of its own transaction (so it's only delivered once that transaction
actually commits), and every server process -- including this one -- picks
it up through its own LISTEN connection and forwards it to the WebSockets it
holds locally.

That means it works the same way whether the write and the open page are
served by the same server process or by several behind a load balancer --
each is just another LISTENer, with no extra setup -- as long as every
process that writes to patient_documents also calls emit_event().
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "documents_changes"


class _WebSocketGroups:
    """A set of WebSockets per key (doctor profile id, or document id)."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    def add(self, key: UUID, websocket: WebSocket) -> None:
        self._connections[key].add(websocket)

    def remove(self, key: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(key)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(key, None)

    async def broadcast(self, key: UUID, payload: dict) -> None:
        connections = list(self._connections.get(key, ()))
        if not connections:
            return
        results = await asyncio.gather(
            *(ws.send_json(payload) for ws in connections), return_exceptions=True
        )
        for ws, result in zip(connections, results):
            if isinstance(result, Exception):
                self.remove(key, ws)


class DocumentEventsManager:
    """This process's local WebSocket connections. Fed only by
    PostgresEventBridge below -- never call `broadcast` directly from a
    route/controller, call `emit_event`.

    Two independent groupings share the same underlying events:
    - by doctor profile: the authenticated Documents page (a doctor and
      their staff see every one of the doctor's documents change).
    - by document id: the public, no-login share pages -- the patient
      fill-in link and the doctor-to-doctor read-only link -- which must
      only ever learn about the ONE document their token is for, never the
      doctor's other documents.
    """

    def __init__(self) -> None:
        self._by_doctor = _WebSocketGroups()
        self._by_document = _WebSocketGroups()

    def add(self, doctor_profile_id: UUID, websocket: WebSocket) -> None:
        self._by_doctor.add(doctor_profile_id, websocket)

    def remove(self, doctor_profile_id: UUID, websocket: WebSocket) -> None:
        self._by_doctor.remove(doctor_profile_id, websocket)

    def add_document(self, document_id: UUID, websocket: WebSocket) -> None:
        self._by_document.add(document_id, websocket)

    def remove_document(self, document_id: UUID, websocket: WebSocket) -> None:
        self._by_document.remove(document_id, websocket)

    async def broadcast(self, doctor_profile_id: UUID, payload: dict) -> None:
        await self._by_doctor.broadcast(doctor_profile_id, payload)
        document_id = payload.get("document_id")
        if document_id:
            try:
                await self._by_document.broadcast(UUID(document_id), payload)
            except ValueError:
                pass


document_events = DocumentEventsManager()


async def emit_event(db: AsyncSession, doctor_profile_id: UUID | None, event: dict[str, Any]) -> None:
    """Call this after any write that a doctor's Documents page should know
    about, inside the same transaction as the write (before commit) so the
    notification is only delivered once that write is actually visible to
    other connections -- Postgres queues NOTIFY until COMMIT.

    Never raises -- a failed notification must not fail the write itself.
    """
    if doctor_profile_id is None:
        return
    try:
        payload = json.dumps({**event, "doctor_profile_id": str(doctor_profile_id)})
        await db.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": NOTIFY_CHANNEL, "payload": payload})
    except Exception:
        logger.exception("Failed to publish document event")


class PostgresEventBridge:
    """Owns one dedicated connection LISTENing on documents_changes and
    forwards every notification to this process's DocumentEventsManager.
    A LISTEN connection is single-purpose -- it must never be shared with the
    app's normal pooled queries -- so this opens its own raw asyncpg
    connection outside the SQLAlchemy pool, started in the app's lifespan.
    """

    def __init__(self, dsn: str) -> None:
        # asyncpg.connect() takes a plain postgresql:// DSN, not SQLAlchemy's
        # "+asyncpg" dialect form.
        self._dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._conn: asyncpg.Connection | None = None

    async def start(self) -> None:
        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.add_listener(NOTIFY_CHANNEL, self._on_notify)
        logger.info("Listening for document events on Postgres channel %r", NOTIFY_CHANNEL)

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.remove_listener(NOTIFY_CHANNEL, self._on_notify)
            await self._conn.close()
            self._conn = None

    def _on_notify(self, connection, pid, channel, payload: str) -> None:
        # asyncpg calls this synchronously; hand the actual work to the loop.
        asyncio.create_task(self._handle(payload))

    async def _handle(self, payload: str) -> None:
        try:
            data = json.loads(payload)
            doctor_profile_id = UUID(data.pop("doctor_profile_id"))
        except Exception:
            logger.exception("Malformed document event payload: %r", payload)
            return
        await document_events.broadcast(doctor_profile_id, data)
