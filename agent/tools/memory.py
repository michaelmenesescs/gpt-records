"""
Vector memory search tools — Claude uses these to recall similar past items.

Four search surfaces:
  search_similar_venues    — semantic venue discovery
  search_similar_outreach  — find proven email templates / avoid duplicates
  search_similar_posts     — surface past content for voice consistency
  search_past_strategies   — retrieve relevant past week strategies
"""
import json
from typing import Optional

from memory.qdrant_store import (
    search_venues,
    search_outreach,
    search_social_posts,
    search_strategies,
)


# ---------------------------------------------------------------------------
# Tool definitions (Claude schema)
# ---------------------------------------------------------------------------

MEMORY_TOOL_DEFINITIONS = [
    {
        "name": "search_similar_venues",
        "description": (
            "Semantically search the venue database using natural language. "
            "Finds venues whose profile (name, city, genres, notes) best matches the query. "
            "Use this to discover booking targets: e.g. 'underground techno clubs in Berlin under 1000 cap'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of venues you're looking for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_similar_outreach",
        "description": (
            "Find past outreach emails semantically similar to a query or draft. "
            "Use before drafting a new email to: (1) find what worked before, "
            "(2) check if we've already contacted this promoter recently, "
            "(3) avoid near-duplicate sends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Email draft, venue name, or topic to search for similar past outreach",
                },
                "status_filter": {
                    "type": "string",
                    "description": "Only return emails with this status (e.g. 'booked' to find successful templates)",
                },
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_similar_posts",
        "description": (
            "Find past social media posts similar to what you're about to write. "
            "Use this to: (1) maintain consistent voice and style, "
            "(2) avoid repeating content, "
            "(3) find high-performing post patterns to reuse."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or draft content to find similar past posts",
                },
                "platform": {
                    "type": "string",
                    "description": "Filter by platform: instagram, twitter, soundcloud, etc.",
                },
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_past_strategies",
        "description": (
            "Retrieve past weekly strategies relevant to a topic or goal. "
            "Use when generating a new strategy to avoid repeating old plans "
            "and to build on what has worked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or goal to find relevant past strategies for",
                },
                "limit": {"type": "integer", "description": "Max results (default 3)"},
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def search_similar_venues_tool(query: str, limit: int = 5) -> str:
    try:
        results = search_venues(query, limit=limit)
        if not results:
            return json.dumps({"results": [], "message": "No similar venues found in memory."})
        return json.dumps({"results": results, "count": len(results)})
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {e}"})


def search_similar_outreach_tool(query: str, status_filter: str = None, limit: int = 5) -> str:
    try:
        results = search_outreach(query, limit=limit, status=status_filter)
        if not results:
            return json.dumps({"results": [], "message": "No similar outreach found in memory."})
        return json.dumps({"results": results, "count": len(results)})
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {e}"})


def search_similar_posts_tool(query: str, platform: str = None, limit: int = 5) -> str:
    try:
        results = search_social_posts(query, limit=limit, platform=platform)
        if not results:
            return json.dumps({"results": [], "message": "No similar posts found in memory."})
        return json.dumps({"results": results, "count": len(results)})
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {e}"})


def search_past_strategies_tool(query: str, limit: int = 3) -> str:
    try:
        results = search_strategies(query, limit=limit)
        if not results:
            return json.dumps({"results": [], "message": "No past strategies found in memory."})
        return json.dumps({"results": results, "count": len(results)})
    except Exception as e:
        return json.dumps({"error": f"Vector search failed: {e}"})
