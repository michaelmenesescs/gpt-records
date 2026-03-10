"""
Social media content tools: save and retrieve posts.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from db.models import SocialPost


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

SOCIAL_TOOL_DEFINITIONS = [
    {
        "name": "save_social_post",
        "description": (
            "Save a generated social media post to the database. "
            "Call this after drafting content for a platform."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform name",
                    "enum": [
                        "instagram",
                        "twitter",
                        "facebook",
                        "soundcloud",
                        "mixcloud",
                        "tiktok",
                        "youtube",
                        "resident_advisor",
                    ],
                },
                "content": {
                    "type": "string",
                    "description": "The post content / caption",
                },
                "hashtags": {
                    "type": "string",
                    "description": "Hashtag string to append, e.g. '#techno #electronicmusic'",
                },
                "post_type": {
                    "type": "string",
                    "description": "Category: announcement, mix-release, promo, event, repost-request, bio-update",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "ISO-8601 datetime to schedule the post, e.g. '2025-03-15T18:00:00'",
                },
                "notes": {"type": "string", "description": "Internal notes"},
            },
            "required": ["platform", "content"],
        },
    },
    {
        "name": "get_recent_posts",
        "description": "Retrieve recently generated social media posts from the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Filter by platform"},
                "post_type": {"type": "string", "description": "Filter by post type"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "generate_content_brief",
        "description": (
            "Generate a structured content brief describing what social posts to create "
            "for the current week. Returns a JSON plan with platforms, themes, and targets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "Primary focus this week, e.g. 'new mix release', 'gig announcement', 'listener growth'",
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target platforms for content",
                },
                "upcoming_events": {
                    "type": "string",
                    "description": "Any upcoming gigs or releases to promote",
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def save_social_post(
    db: Session,
    platform: str,
    content: str,
    hashtags: str = None,
    post_type: str = None,
    scheduled_at: str = None,
    notes: str = None,
) -> str:
    scheduled = None
    if scheduled_at:
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass

    post = SocialPost(
        platform=platform,
        content=content,
        hashtags=hashtags,
        post_type=post_type,
        scheduled_at=scheduled,
        notes=notes,
    )
    db.add(post)
    db.flush()
    return json.dumps({
        "status": "saved",
        "post_id": post.id,
        "platform": platform,
        "scheduled_at": scheduled_at,
    })


def get_recent_posts(
    db: Session,
    platform: str = None,
    post_type: str = None,
    limit: int = 10,
) -> str:
    query = db.query(SocialPost)
    if platform:
        query = query.filter(SocialPost.platform == platform)
    if post_type:
        query = query.filter(SocialPost.post_type == post_type)

    posts = query.order_by(SocialPost.created_at.desc()).limit(limit).all()
    results = [
        {
            "id": p.id,
            "platform": p.platform,
            "post_type": p.post_type,
            "content": p.content[:200] + ("..." if len(p.content) > 200 else ""),
            "hashtags": p.hashtags,
            "created_at": p.created_at.strftime("%Y-%m-%d"),
            "scheduled_at": p.scheduled_at.strftime("%Y-%m-%d %H:%M") if p.scheduled_at else None,
            "posted_at": p.posted_at.strftime("%Y-%m-%d") if p.posted_at else None,
        }
        for p in posts
    ]
    return json.dumps({"posts": results, "count": len(results)})


def generate_content_brief(
    db: Session,
    focus: str = None,
    platforms: list = None,
    upcoming_events: str = None,
) -> str:
    """Returns context for the AI to build a content plan from."""
    recent_count = db.query(SocialPost).filter(
        SocialPost.created_at >= datetime.utcnow().replace(day=1)
    ).count()

    context = {
        "action": "generate_content_brief",
        "focus": focus or "general promotion and listener growth",
        "platforms": platforms or ["instagram", "soundcloud", "mixcloud"],
        "upcoming_events": upcoming_events,
        "posts_this_month": recent_count,
        "instruction": (
            "Create a weekly content calendar with specific post ideas, "
            "suggested copy, hashtag sets, and optimal posting times. "
            "Align with the artist's genre and growth targets."
        ),
    }
    return json.dumps(context)
