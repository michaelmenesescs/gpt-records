"""
FastAPI application — Agent API layer.

Endpoints:
  POST /api/chat          — conversational agent (streaming SSE)
  POST /api/chat/sync     — conversational agent (blocking)
  GET  /api/pipeline      — current outreach pipeline
  POST /api/pipeline      — record new outreach
  PATCH /api/pipeline/{id}— update outreach status
  GET  /api/venues        — list venues
  POST /api/venues        — add venue
  GET  /api/metrics       — metrics history
  POST /api/metrics       — log metrics snapshot
  GET  /api/strategies    — recent weekly strategies
  POST /api/strategies    — generate + save strategy
  GET  /api/reminders     — overdue follow-up reminders
  GET  /health            — liveness check
"""
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import get_settings
from db.session import init_db, db_session
from db.models import OutreachStatus
from memory.qdrant_store import init_collections
from agents.manager import ArtistManagerAgent
from tools.booking import add_venue as _add_venue, search_venues as _search_venues
from tools.outreach import (
    get_outreach_pipeline as _get_pipeline,
    record_outreach as _record_outreach,
    update_outreach as _update_outreach,
    get_follow_up_reminders as _get_reminders,
)
from tools.metrics import (
    get_metrics_history as _get_metrics,
    log_metrics as _log_metrics,
    get_recent_strategies as _get_strategies,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        init_collections()
    except Exception as e:
        # Qdrant might not be ready yet on first boot — non-fatal
        print(f"[warning] Qdrant init skipped: {e}")
    yield


app = FastAPI(
    title="GPT Records — AI Artist Manager",
    description="Local AI agent platform for music promotion and booking",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

# One agent per "session" — for MVP we use a single global instance.
# In production this should be session-scoped.
_agent = ArtistManagerAgent(settings)


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    reset_history: bool = False


class VenueCreate(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    genres: Optional[str] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None


class OutreachCreate(BaseModel):
    promoter_name: str
    contact_email: str
    email_subject: str
    venue_id: Optional[int] = None
    email_body: Optional[str] = None
    follow_up_days: int = 7
    notes: Optional[str] = None


class OutreachUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    follow_up_days: Optional[int] = None


class MetricsCreate(BaseModel):
    monthly_listeners: Optional[int] = None
    soundcloud_followers: Optional[int] = None
    instagram_followers: Optional[int] = None
    mixcloud_followers: Optional[int] = None
    resident_advisor_followers: Optional[int] = None
    bandcamp_sales: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------


@app.post("/api/chat")
async def chat_stream(req: ChatRequest):
    """Stream the agent response via Server-Sent Events."""
    if req.reset_history:
        _agent.reset()

    def generate():
        try:
            for chunk in _agent.chat_stream(req.message):
                data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat/sync")
async def chat_sync(req: ChatRequest):
    """Non-streaming chat — waits for the full response."""
    if req.reset_history:
        _agent.reset()
    try:
        response = _agent.chat(req.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Pipeline / Outreach endpoints
# ---------------------------------------------------------------------------


@app.get("/api/pipeline")
def get_pipeline(
    status: Optional[str] = Query(None),
    include_booked: bool = Query(False),
):
    with db_session() as db:
        result = _get_pipeline(db, status=status, include_booked=include_booked)
    return json.loads(result)


@app.post("/api/pipeline", status_code=201)
def create_outreach(body: OutreachCreate):
    with db_session() as db:
        result = _record_outreach(db, **body.model_dump())
    return json.loads(result)


@app.patch("/api/pipeline/{outreach_id}")
def update_pipeline(outreach_id: int, body: OutreachUpdate):
    with db_session() as db:
        result = _update_outreach(db, outreach_id=outreach_id, **body.model_dump(exclude_none=True))
    data = json.loads(result)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/reminders")
def get_reminders(days_ahead: int = Query(3)):
    with db_session() as db:
        result = _get_reminders(db, days_ahead=days_ahead)
    return json.loads(result)


# ---------------------------------------------------------------------------
# Venues endpoints
# ---------------------------------------------------------------------------


@app.get("/api/venues")
def list_venues(
    city: Optional[str] = None,
    country: Optional[str] = None,
    genre: Optional[str] = None,
    limit: int = Query(20, le=100),
):
    with db_session() as db:
        result = _search_venues(db, city=city, country=country, genre=genre, limit=limit)
    return json.loads(result)


@app.post("/api/venues", status_code=201)
def create_venue(body: VenueCreate):
    with db_session() as db:
        result = _add_venue(db, **body.model_dump())
    return json.loads(result)


# ---------------------------------------------------------------------------
# Metrics endpoints
# ---------------------------------------------------------------------------


@app.get("/api/metrics")
def get_metrics(days: int = Query(90)):
    with db_session() as db:
        result = _get_metrics(db, days=days)
    return json.loads(result)


@app.post("/api/metrics", status_code=201)
def log_metrics_snapshot(body: MetricsCreate):
    with db_session() as db:
        from tools.metrics import log_metrics
        result = log_metrics(db, **body.model_dump())
    return json.loads(result)


# ---------------------------------------------------------------------------
# Weekly strategy endpoints
# ---------------------------------------------------------------------------


@app.get("/api/strategies")
def get_strategies(limit: int = Query(4)):
    with db_session() as db:
        result = _get_strategies(db, limit=limit)
    return json.loads(result)


@app.post("/api/strategies/generate")
async def generate_strategy():
    """Ask the agent to generate and save a weekly strategy."""
    try:
        response = _agent.chat(
            "Generate a detailed weekly promotion strategy for this week. "
            "Check the current outreach pipeline and metrics first, "
            "then create a concrete action plan. Save the strategy when done."
        )
        return {"strategy": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "artist": settings.artist_name}
