"""
Metrics tools: log and analyse growth data.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import MetricEntry, OutreachRecord, OutreachStatus, WeeklyStrategy


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

METRICS_TOOL_DEFINITIONS = [
    {
        "name": "log_metrics",
        "description": (
            "Log a snapshot of current growth metrics. "
            "Call this when you have fresh numbers to record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "monthly_listeners": {
                    "type": "integer",
                    "description": "Spotify/Apple Music monthly listeners",
                },
                "soundcloud_followers": {"type": "integer"},
                "instagram_followers": {"type": "integer"},
                "mixcloud_followers": {"type": "integer"},
                "resident_advisor_followers": {"type": "integer"},
                "bandcamp_sales": {"type": "integer", "description": "Total Bandcamp sales"},
                "notes": {"type": "string", "description": "Context or notes about this snapshot"},
            },
        },
    },
    {
        "name": "get_metrics_history",
        "description": "Retrieve the metrics history for trend analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history to retrieve (default 90)",
                }
            },
        },
    },
    {
        "name": "get_progress_report",
        "description": (
            "Generate a comprehensive progress report covering growth metrics, "
            "outreach pipeline stats, and progress against booking and listener goals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Whether to request AI recommendations (default true)",
                }
            },
        },
    },
    {
        "name": "save_weekly_strategy",
        "description": "Persist a generated weekly strategy to the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "week_of": {
                    "type": "string",
                    "description": "ISO date of the Monday for this week, e.g. '2025-03-10'",
                },
                "strategy": {
                    "type": "string",
                    "description": "Full strategy text",
                },
                "goals": {
                    "type": "string",
                    "description": "Specific measurable goals for the week",
                },
            },
            "required": ["strategy"],
        },
    },
    {
        "name": "get_recent_strategies",
        "description": "Retrieve recent weekly strategies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of strategies to return (default 4)"}
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def log_metrics(
    db: Session,
    monthly_listeners: int = None,
    soundcloud_followers: int = None,
    instagram_followers: int = None,
    mixcloud_followers: int = None,
    resident_advisor_followers: int = None,
    bandcamp_sales: int = None,
    notes: str = None,
) -> str:
    entry = MetricEntry(
        monthly_listeners=monthly_listeners,
        soundcloud_followers=soundcloud_followers,
        instagram_followers=instagram_followers,
        mixcloud_followers=mixcloud_followers,
        resident_advisor_followers=resident_advisor_followers,
        bandcamp_sales=bandcamp_sales,
        notes=notes,
    )
    db.add(entry)
    db.flush()
    return json.dumps({"status": "logged", "entry_id": entry.id, "recorded_at": entry.recorded_at.strftime("%Y-%m-%d %H:%M")})


def get_metrics_history(db: Session, days: int = 90) -> str:
    since = datetime.utcnow() - timedelta(days=days)
    entries = (
        db.query(MetricEntry)
        .filter(MetricEntry.recorded_at >= since)
        .order_by(MetricEntry.recorded_at.desc())
        .all()
    )
    results = [
        {
            "id": e.id,
            "recorded_at": e.recorded_at.strftime("%Y-%m-%d"),
            "monthly_listeners": e.monthly_listeners,
            "soundcloud_followers": e.soundcloud_followers,
            "instagram_followers": e.instagram_followers,
            "mixcloud_followers": e.mixcloud_followers,
            "resident_advisor_followers": e.resident_advisor_followers,
            "bandcamp_sales": e.bandcamp_sales,
            "notes": e.notes,
        }
        for e in entries
    ]
    return json.dumps({"entries": results, "count": len(results), "days": days})


def get_progress_report(db: Session, include_recommendations: bool = True) -> str:
    # Latest metrics
    latest = db.query(MetricEntry).order_by(MetricEntry.recorded_at.desc()).first()

    # Outreach stats
    total_outreach = db.query(func.count(OutreachRecord.id)).scalar()
    booked = db.query(func.count(OutreachRecord.id)).filter(
        OutreachRecord.status == OutreachStatus.BOOKED
    ).scalar()
    active = db.query(func.count(OutreachRecord.id)).filter(
        OutreachRecord.status.in_([
            OutreachStatus.CONTACTED,
            OutreachStatus.FOLLOW_UP_SENT,
            OutreachStatus.RESPONDED_POSITIVE,
        ])
    ).scalar()

    report = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "goals": {
            "gigs_target": "5–10 gigs by summer",
            "listeners_mid_year": 300,
            "listeners_end_year": 1000,
        },
        "current_metrics": {
            "monthly_listeners": latest.monthly_listeners if latest else None,
            "soundcloud_followers": latest.soundcloud_followers if latest else None,
            "instagram_followers": latest.instagram_followers if latest else None,
            "last_recorded": latest.recorded_at.strftime("%Y-%m-%d") if latest else "never",
        },
        "booking_pipeline": {
            "total_outreach": total_outreach,
            "gigs_booked": booked,
            "active_conversations": active,
        },
        "include_recommendations": include_recommendations,
    }
    return json.dumps(report)


def save_weekly_strategy(
    db: Session,
    strategy: str,
    week_of: str = None,
    goals: str = None,
) -> str:
    if week_of:
        week_dt = datetime.fromisoformat(week_of)
    else:
        today = datetime.utcnow()
        week_dt = today - timedelta(days=today.weekday())  # Monday

    ws = WeeklyStrategy(
        week_of=week_dt,
        strategy=strategy,
        goals=goals,
    )
    db.add(ws)
    db.flush()

    # Auto-embed into vector memory
    try:
        from memory.qdrant_store import upsert_strategy
        upsert_strategy(
            strategy_id=ws.id,
            week_of=week_dt.strftime("%Y-%m-%d"),
            goals=goals or "",
            strategy_text=strategy,
        )
    except Exception:
        pass

    return json.dumps({"status": "saved", "strategy_id": ws.id, "week_of": week_dt.strftime("%Y-%m-%d")})


def get_recent_strategies(db: Session, limit: int = 4) -> str:
    strategies = (
        db.query(WeeklyStrategy)
        .order_by(WeeklyStrategy.week_of.desc())
        .limit(limit)
        .all()
    )
    results = [
        {
            "id": s.id,
            "week_of": s.week_of.strftime("%Y-%m-%d"),
            "goals": s.goals,
            "strategy_excerpt": s.strategy[:300] + ("..." if len(s.strategy) > 300 else ""),
            "completed": s.completed,
            "created_at": s.created_at.strftime("%Y-%m-%d"),
        }
        for s in strategies
    ]
    return json.dumps({"strategies": results, "count": len(results)})
