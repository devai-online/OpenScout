"""Single-session lead-gen runner. One job at a time, broadcast events to subscribers."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from db.session import get_db
from db.models import SearchSession, Lead
from scraper.engine import run_search


class _Hub:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.current_session_id: Optional[int] = None
        self.task: Optional[asyncio.Task] = None
        self.subscribers: list[asyncio.Queue] = []
        self.history_buffer: list[dict] = []  # events for current session, replayed to new subs

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # replay buffered events so a late-joining UI sees prior leads
        for ev in self.history_buffer:
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                break
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def broadcast(self, event: dict):
        self.history_buffer.append(event)
        if len(self.history_buffer) > 2000:
            self.history_buffer = self.history_buffer[-1500:]
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()


hub = _Hub()


async def _log_to_db(session_id: int, line: str):
    with get_db() as db:
        s = db.get(SearchSession, session_id)
        if s:
            s.log = (s.log or "") + line + "\n"


async def _job(session_id: int, params: dict):
    async def log_cb(msg: str):
        await hub.broadcast({"type": "log", "msg": msg})
        await _log_to_db(session_id, msg)

    leads_count = 0
    try:
        async for lead in run_search(
            domain=params["domain"],
            country=params["country"],
            min_emp=params["min_emp"],
            max_emp=params["max_emp"],
            limit=params["limit"],
            notes=params.get("notes", ""),
            log_cb=log_cb,
        ):
            with get_db() as db:
                row = Lead(session_id=session_id, **lead)
                db.add(row)
                db.flush()
                lead_payload = {
                    "id": row.id,
                    "session_id": session_id,
                    **lead,
                }
            leads_count += 1
            await hub.broadcast({"type": "lead", "lead": lead_payload})

        status = "completed"
    except asyncio.CancelledError:
        status = "cancelled"
        await hub.broadcast({"type": "log", "msg": "Search cancelled."})
        raise
    except Exception as e:
        status = "error"
        await hub.broadcast({"type": "log", "msg": f"ERROR: {e}"})
        await _log_to_db(session_id, f"ERROR: {e}")
    finally:
        with get_db() as db:
            s = db.get(SearchSession, session_id)
            if s:
                s.status = status
                s.lead_count = leads_count
                s.finished_at = datetime.now(timezone.utc)
        await hub.broadcast({"type": "done", "session_id": session_id, "status": status, "lead_count": leads_count})
        hub.current_session_id = None
        hub.history_buffer.clear()


async def start(params: dict) -> int:
    """Returns session_id. Raises if already running."""
    async with hub.lock:
        if hub.is_running():
            raise RuntimeError("A search is already running. Wait for it to finish.")
        with get_db() as db:
            s = SearchSession(
                domain=params["domain"],
                country=params["country"],
                min_emp=params["min_emp"],
                max_emp=params["max_emp"],
                limit=params["limit"],
                notes=params.get("notes", ""),
                status="running",
            )
            db.add(s)
            db.flush()
            session_id = s.id

        hub.current_session_id = session_id
        hub.history_buffer.clear()
        await hub.broadcast({"type": "start", "session_id": session_id, "params": params})
        hub.task = asyncio.create_task(_job(session_id, params))
        return session_id


async def cancel():
    if hub.task and not hub.task.done():
        hub.task.cancel()
