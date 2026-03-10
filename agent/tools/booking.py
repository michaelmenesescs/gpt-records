"""
Booking tools: venue management and email drafting.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from db.models import Venue


# ---------------------------------------------------------------------------
# Tool definitions (Claude schema)
# ---------------------------------------------------------------------------

BOOKING_TOOL_DEFINITIONS = [
    {
        "name": "add_venue",
        "description": (
            "Add a new venue or promoter to the tracking database. "
            "Use this when you identify a new booking target."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Venue or promoter name"},
                "city": {"type": "string", "description": "City the venue is in"},
                "country": {"type": "string", "description": "Country"},
                "contact_name": {"type": "string", "description": "Name of the booking contact"},
                "contact_email": {"type": "string", "description": "Booking contact email"},
                "website": {"type": "string", "description": "Venue website URL"},
                "genres": {
                    "type": "string",
                    "description": "Comma-separated genre tags, e.g. 'techno, house, electronic'",
                },
                "capacity": {"type": "integer", "description": "Approximate venue capacity"},
                "notes": {"type": "string", "description": "Any additional notes"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "search_venues",
        "description": "Search venues in the database by city, country, or genre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Filter by city"},
                "country": {"type": "string", "description": "Filter by country"},
                "genre": {"type": "string", "description": "Filter by genre keyword"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 20)",
                },
            },
        },
    },
    {
        "name": "draft_booking_email",
        "description": (
            "Draft a personalised booking inquiry email for a venue or promoter. "
            "Returns a subject line and email body ready to send."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "venue_name": {"type": "string", "description": "Name of the venue/promoter"},
                "contact_name": {"type": "string", "description": "Name of the booking contact (optional)"},
                "city": {"type": "string", "description": "City of the venue"},
                "artist_achievements": {
                    "type": "string",
                    "description": "Recent achievements to highlight (releases, plays, previous gigs)",
                },
                "proposed_dates": {
                    "type": "string",
                    "description": "Proposed date range or flexibility window",
                },
                "fee_range": {
                    "type": "string",
                    "description": "Fee expectation or range (optional)",
                },
                "set_length": {
                    "type": "string",
                    "description": "Preferred set length e.g. '2 hours'",
                },
                "tone": {
                    "type": "string",
                    "description": "Email tone: 'professional', 'casual', or 'warm'",
                    "enum": ["professional", "casual", "warm"],
                },
            },
            "required": ["venue_name"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def add_venue(db: Session, name: str, city: str = None, country: str = None,
              contact_name: str = None, contact_email: str = None,
              website: str = None, genres: str = None, capacity: int = None,
              notes: str = None) -> str:
    venue = Venue(
        name=name,
        city=city,
        country=country,
        contact_name=contact_name,
        contact_email=contact_email,
        website=website,
        genres=genres,
        capacity=capacity,
        notes=notes,
    )
    db.add(venue)
    db.flush()

    # Auto-embed into vector memory (best-effort — never block the write)
    try:
        from memory.qdrant_store import upsert_venue
        upsert_venue(
            venue_id=venue.id,
            name=name,
            city=city or "",
            country=country or "",
            genres=genres or "",
            notes=notes or "",
        )
    except Exception:
        pass

    return json.dumps({
        "status": "created",
        "venue_id": venue.id,
        "name": venue.name,
        "city": venue.city,
    })


def search_venues(db: Session, city: str = None, country: str = None,
                  genre: str = None, limit: int = 20) -> str:
    query = db.query(Venue)
    if city:
        query = query.filter(Venue.city.ilike(f"%{city}%"))
    if country:
        query = query.filter(Venue.country.ilike(f"%{country}%"))
    if genre:
        query = query.filter(Venue.genres.ilike(f"%{genre}%"))

    venues = query.order_by(Venue.created_at.desc()).limit(limit).all()

    if not venues:
        return json.dumps({"venues": [], "count": 0, "message": "No venues found."})

    results = [
        {
            "id": v.id,
            "name": v.name,
            "city": v.city,
            "country": v.country,
            "contact_name": v.contact_name,
            "contact_email": v.contact_email,
            "genres": v.genres,
            "capacity": v.capacity,
            "notes": v.notes,
        }
        for v in venues
    ]
    return json.dumps({"venues": results, "count": len(results)})


def draft_booking_email(
    db: Session,
    venue_name: str,
    contact_name: str = None,
    city: str = None,
    artist_achievements: str = None,
    proposed_dates: str = None,
    fee_range: str = None,
    set_length: str = None,
    tone: str = "professional",
) -> str:
    """
    Returns a structured dict with subject and body.
    The actual AI drafting happens in the agent layer via Claude — this tool
    returns a prompt scaffold that the calling agent uses to generate the email.
    """
    prompt_context = {
        "action": "draft_booking_email",
        "venue_name": venue_name,
        "contact_name": contact_name,
        "city": city,
        "artist_achievements": artist_achievements,
        "proposed_dates": proposed_dates,
        "fee_range": fee_range,
        "set_length": set_length or "2-3 hours",
        "tone": tone,
        "instruction": (
            "Using the artist profile from your system context, draft a compelling "
            "booking inquiry email. Return JSON with keys 'subject' and 'body'."
        ),
    }
    return json.dumps(prompt_context)
