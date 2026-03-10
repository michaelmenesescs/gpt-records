"""
Outreach tracking tools: log contacts, update statuses, view pipeline.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from db.models import OutreachRecord, OutreachStatus, Venue


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

OUTREACH_TOOL_DEFINITIONS = [
    {
        "name": "record_outreach",
        "description": (
            "Log a new outreach contact attempt with a venue or promoter. "
            "Call this after sending a booking email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "venue_id": {
                    "type": "integer",
                    "description": "ID of the venue (if it exists in the database)",
                },
                "promoter_name": {
                    "type": "string",
                    "description": "Name of venue or promoter contacted",
                },
                "contact_email": {"type": "string", "description": "Email address contacted"},
                "email_subject": {"type": "string", "description": "Subject line of the email sent"},
                "email_body": {"type": "string", "description": "Full body of the email sent"},
                "follow_up_days": {
                    "type": "integer",
                    "description": "Days until follow-up reminder (default 7)",
                },
                "notes": {"type": "string", "description": "Any additional notes"},
            },
            "required": ["promoter_name", "contact_email", "email_subject"],
        },
    },
    {
        "name": "update_outreach",
        "description": (
            "Update the status or notes of an existing outreach record. "
            "Use when a venue replies, you send a follow-up, or a gig is booked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "outreach_id": {
                    "type": "integer",
                    "description": "ID of the outreach record to update",
                },
                "status": {
                    "type": "string",
                    "description": "New status",
                    "enum": [s.value for s in OutreachStatus],
                },
                "notes": {"type": "string", "description": "Updated notes or response summary"},
                "follow_up_days": {
                    "type": "integer",
                    "description": "Reset follow-up reminder N days from now",
                },
            },
            "required": ["outreach_id"],
        },
    },
    {
        "name": "get_outreach_pipeline",
        "description": (
            "Get the current outreach pipeline — all contacts and their statuses. "
            "Optionally filter by status. Also flags any overdue follow-ups."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (leave empty for all)",
                    "enum": [s.value for s in OutreachStatus],
                },
                "include_booked": {
                    "type": "boolean",
                    "description": "Include already-booked gigs (default false)",
                },
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
        },
    },
    {
        "name": "get_follow_up_reminders",
        "description": "Get outreach records that are due for a follow-up today or overdue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Include follow-ups due within N days (default 3)",
                }
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def record_outreach(
    db: Session,
    promoter_name: str,
    contact_email: str,
    email_subject: str,
    venue_id: int = None,
    email_body: str = None,
    follow_up_days: int = 7,
    notes: str = None,
) -> str:
    now = datetime.utcnow()
    record = OutreachRecord(
        venue_id=venue_id,
        promoter_name=promoter_name,
        contact_email=contact_email,
        email_subject=email_subject,
        email_body=email_body,
        status=OutreachStatus.CONTACTED,
        contacted_at=now,
        follow_up_at=now + timedelta(days=follow_up_days),
        notes=notes,
    )
    db.add(record)
    db.flush()
    return json.dumps({
        "status": "recorded",
        "outreach_id": record.id,
        "promoter": promoter_name,
        "follow_up_date": record.follow_up_at.strftime("%Y-%m-%d"),
    })


def update_outreach(
    db: Session,
    outreach_id: int,
    status: str = None,
    notes: str = None,
    follow_up_days: int = None,
) -> str:
    record = db.query(OutreachRecord).filter(OutreachRecord.id == outreach_id).first()
    if not record:
        return json.dumps({"error": f"Outreach record {outreach_id} not found."})

    if status:
        record.status = status
    if notes:
        existing = record.notes or ""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        record.notes = f"{existing}\n[{timestamp}] {notes}".strip()
    if follow_up_days is not None:
        record.follow_up_at = datetime.utcnow() + timedelta(days=follow_up_days)

    record.last_updated = datetime.utcnow()
    return json.dumps({
        "status": "updated",
        "outreach_id": outreach_id,
        "new_status": record.status,
        "follow_up_date": record.follow_up_at.strftime("%Y-%m-%d") if record.follow_up_at else None,
    })


def get_outreach_pipeline(
    db: Session,
    status: str = None,
    include_booked: bool = False,
    limit: int = 50,
) -> str:
    query = db.query(OutreachRecord)

    if status:
        query = query.filter(OutreachRecord.status == status)
    elif not include_booked:
        query = query.filter(OutreachRecord.status != OutreachStatus.BOOKED)

    records = query.order_by(OutreachRecord.last_updated.desc()).limit(limit).all()
    now = datetime.utcnow()

    results = []
    for r in records:
        is_overdue = (
            r.follow_up_at and r.follow_up_at < now
            and r.status not in (OutreachStatus.BOOKED, OutreachStatus.RESPONDED_NEGATIVE)
        )
        results.append({
            "id": r.id,
            "promoter": r.promoter_name,
            "email": r.contact_email,
            "subject": r.email_subject,
            "status": r.status,
            "contacted_at": r.contacted_at.strftime("%Y-%m-%d") if r.contacted_at else None,
            "follow_up_at": r.follow_up_at.strftime("%Y-%m-%d") if r.follow_up_at else None,
            "overdue_follow_up": is_overdue,
            "notes": r.notes,
        })

    summary = {
        "total": len(results),
        "by_status": {},
        "overdue_follow_ups": sum(1 for r in results if r["overdue_follow_up"]),
    }
    for r in results:
        s = r["status"]
        summary["by_status"][s] = summary["by_status"].get(s, 0) + 1

    return json.dumps({"pipeline": results, "summary": summary})


def get_follow_up_reminders(db: Session, days_ahead: int = 3) -> str:
    cutoff = datetime.utcnow() + timedelta(days=days_ahead)
    records = (
        db.query(OutreachRecord)
        .filter(
            OutreachRecord.follow_up_at <= cutoff,
            OutreachRecord.status.notin_(
                [OutreachStatus.BOOKED, OutreachStatus.RESPONDED_NEGATIVE]
            ),
        )
        .order_by(OutreachRecord.follow_up_at.asc())
        .all()
    )

    results = [
        {
            "id": r.id,
            "promoter": r.promoter_name,
            "email": r.contact_email,
            "status": r.status,
            "follow_up_at": r.follow_up_at.strftime("%Y-%m-%d") if r.follow_up_at else None,
            "overdue": r.follow_up_at < datetime.utcnow() if r.follow_up_at else False,
        }
        for r in records
    ]
    return json.dumps({"reminders": results, "count": len(results)})
