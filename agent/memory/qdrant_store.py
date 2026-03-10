"""
Qdrant vector store — collections, upsert, and search helpers.

Collections
-----------
venues          Text of venue profile. Payload: id, name, city, genres.
                Use: semantic venue search ("find underground techno clubs in Berlin")

outreach        Text of subject + email body. Payload: id, promoter, status, contacted_at.
                Use: find successful email templates, avoid near-duplicate sends.

social_posts    Text of post content. Payload: id, platform, post_type, created_at.
                Use: maintain voice consistency, avoid content repetition.

strategies      Text of weekly strategy. Payload: id, week_of, goals.
                Use: reference past approaches, spot recurring patterns.
"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config import get_settings
from memory.embedder import EMBEDDING_DIM, embed


# Collection names
COL_VENUES = "venues"
COL_OUTREACH = "outreach"
COL_SOCIAL_POSTS = "social_posts"
COL_STRATEGIES = "strategies"

ALL_COLLECTIONS = [COL_VENUES, COL_OUTREACH, COL_SOCIAL_POSTS, COL_STRATEGIES]


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    """Return a cached Qdrant client."""
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def init_collections() -> None:
    """Create all collections if they don't already exist."""
    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}

    for name in ALL_COLLECTIONS:
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            print(f"[qdrant] created collection: {name}")


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


def _upsert(collection: str, point_id: str, text: str, payload: Dict[str, Any]) -> None:
    """Embed text and upsert a single point."""
    client = get_qdrant()
    vector = embed(text)
    client.upsert(
        collection_name=collection,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def upsert_venue(venue_id: int, name: str, city: str = "", country: str = "",
                 genres: str = "", notes: str = "") -> None:
    text = f"{name} {genres} {city} {country} {notes}".strip()
    _upsert(
        COL_VENUES,
        point_id=str(venue_id),
        text=text,
        payload={
            "venue_id": venue_id,
            "name": name,
            "city": city,
            "country": country,
            "genres": genres,
        },
    )


def upsert_outreach(outreach_id: int, promoter: str, subject: str,
                    body: str = "", status: str = "", contacted_at: str = "") -> None:
    text = f"{subject} {body}".strip()
    _upsert(
        COL_OUTREACH,
        point_id=str(outreach_id),
        text=text,
        payload={
            "outreach_id": outreach_id,
            "promoter": promoter,
            "subject": subject,
            "status": status,
            "contacted_at": contacted_at,
        },
    )


def upsert_social_post(post_id: int, platform: str, post_type: str = "",
                       content: str = "", hashtags: str = "") -> None:
    text = f"{platform} {post_type} {content} {hashtags}".strip()
    _upsert(
        COL_SOCIAL_POSTS,
        point_id=str(post_id),
        text=text,
        payload={
            "post_id": post_id,
            "platform": platform,
            "post_type": post_type,
            "content_preview": content[:200],
        },
    )


def upsert_strategy(strategy_id: int, week_of: str, goals: str = "",
                    strategy_text: str = "") -> None:
    text = f"{goals} {strategy_text}".strip()
    _upsert(
        COL_STRATEGIES,
        point_id=str(strategy_id),
        text=text,
        payload={
            "strategy_id": strategy_id,
            "week_of": week_of,
            "goals": goals,
            "strategy_preview": strategy_text[:300],
        },
    )


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def _search(collection: str, query: str, limit: int = 5,
            filter_: Optional[Filter] = None) -> List[Dict[str, Any]]:
    client = get_qdrant()
    vector = embed(query)
    results = client.search(
        collection_name=collection,
        query_vector=vector,
        query_filter=filter_,
        limit=limit,
        with_payload=True,
    )
    return [{"score": r.score, **r.payload} for r in results]


def search_venues(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Semantic venue search. E.g. 'underground techno clubs in Berlin'."""
    return _search(COL_VENUES, query, limit)


def search_outreach(query: str, limit: int = 5,
                    status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find similar outreach emails. Optionally filter by status."""
    filter_ = None
    if status:
        filter_ = Filter(must=[FieldCondition(key="status", match=MatchValue(value=status))])
    return _search(COL_OUTREACH, query, limit, filter_)


def search_social_posts(query: str, limit: int = 5,
                        platform: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find similar past social posts. Optionally filter by platform."""
    filter_ = None
    if platform:
        filter_ = Filter(must=[FieldCondition(key="platform", match=MatchValue(value=platform))])
    return _search(COL_SOCIAL_POSTS, query, limit, filter_)


def search_strategies(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Find past strategies relevant to a topic."""
    return _search(COL_STRATEGIES, query, limit)
