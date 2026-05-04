import asyncio
import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from db.session import init_db, get_db
from db.models import SearchSession, Lead
from server import runner


UI_DIR = Path(__file__).resolve().parent.parent / "ui"

app = FastAPI(title="LeadFinder", description="Open-source lead-gen tool")


@app.on_event("startup")
async def _startup():
    init_db()


class SearchParams(BaseModel):
    domain: str = Field(min_length=2, max_length=200)
    country: str = Field(default="", max_length=100)
    min_emp: int = Field(default=0, ge=0, le=100000)
    max_emp: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=10, ge=1, le=25)
    notes: str = Field(default="", max_length=1000)


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/search")
async def start_search(params: SearchParams):
    try:
        session_id = await runner.start(params.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"session_id": session_id}


@app.post("/api/cancel")
async def cancel_search():
    await runner.cancel()
    return {"ok": True}


@app.get("/api/status")
async def status():
    return {
        "running": runner.hub.is_running(),
        "session_id": runner.hub.current_session_id,
    }


@app.get("/api/stream")
async def stream(request: Request):
    """SSE: replay current session buffer + live updates."""
    queue = runner.hub.subscribe()

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"event": ev["type"], "data": json.dumps(ev)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            runner.hub.unsubscribe(queue)

    return EventSourceResponse(event_gen())


@app.get("/api/sessions")
async def list_sessions():
    with get_db() as db:
        rows = db.query(SearchSession).order_by(SearchSession.started_at.desc()).limit(200).all()
        return [
            {
                "id": r.id,
                "domain": r.domain,
                "country": r.country,
                "min_emp": r.min_emp,
                "max_emp": r.max_emp,
                "limit": r.limit,
                "status": r.status,
                "lead_count": r.lead_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int):
    with get_db() as db:
        s = db.get(SearchSession, session_id)
        if not s:
            raise HTTPException(404, "Not found")
        leads = db.query(Lead).filter(Lead.session_id == session_id).order_by(Lead.relevance_score.desc()).all()
        return {
            "session": {
                "id": s.id, "domain": s.domain, "country": s.country,
                "min_emp": s.min_emp, "max_emp": s.max_emp, "limit": s.limit,
                "notes": s.notes, "status": s.status, "lead_count": s.lead_count,
                "log": s.log, "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            },
            "leads": [
                {
                    "id": l.id,
                    "company": l.company, "website": l.website, "email": l.email,
                    "phone": l.phone, "contact_person": l.contact_person,
                    "contact_title": l.contact_title, "employee_count": l.employee_count,
                    "country": l.country, "description": l.description,
                    "relevance_score": l.relevance_score,
                    "relevance_reason": l.relevance_reason,
                    "source_url": l.source_url,
                    "found_at": l.found_at.isoformat() if l.found_at else None,
                }
                for l in leads
            ],
        }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    if runner.hub.current_session_id == session_id and runner.hub.is_running():
        raise HTTPException(409, "Cannot delete a running session")
    with get_db() as db:
        s = db.get(SearchSession, session_id)
        if not s:
            raise HTTPException(404, "Not found")
        db.delete(s)
    return {"ok": True}


@app.get("/api/sessions/{session_id}/export.csv")
async def export_csv(session_id: int):
    with get_db() as db:
        s = db.get(SearchSession, session_id)
        if not s:
            raise HTTPException(404, "Not found")
        leads = db.query(Lead).filter(Lead.session_id == session_id).order_by(Lead.relevance_score.desc()).all()

        buf = io.StringIO()
        fields = ["company", "website", "email", "phone", "contact_person", "contact_title",
                  "employee_count", "country", "description", "relevance_score", "source_url"]
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        for l in leads:
            writer.writerow({f: getattr(l, f, "") for f in fields})

    headers = {"Content-Disposition": f'attachment; filename="leads_session_{session_id}.csv"'}
    return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")),
                             media_type="text/csv", headers=headers)


# Static assets
if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")
