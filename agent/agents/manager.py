"""
AI Artist Manager — main agent orchestrator.

Architecture (from spec):
  User → Agent API → Orchestrator → [Booking | Content | Strategy] Agent
                                          ↓
                                    Model Router
                                          ↓
                                   Storage Layer (Postgres)

Each specialised agent is a focused system-prompt + tool subset.
The Orchestrator detects intent and delegates to the right agent.
"""
import json
import sys
from typing import Iterator, Optional

import anthropic

from config import Settings
from db.session import db_session
from tools.booking import BOOKING_TOOL_DEFINITIONS, add_venue, search_venues, draft_booking_email
from tools.outreach import (
    OUTREACH_TOOL_DEFINITIONS,
    get_follow_up_reminders,
    get_outreach_pipeline,
    record_outreach,
    update_outreach,
)
from tools.social import SOCIAL_TOOL_DEFINITIONS, generate_content_brief, get_recent_posts, save_social_post
from tools.metrics import (
    METRICS_TOOL_DEFINITIONS,
    get_metrics_history,
    get_progress_report,
    get_recent_strategies,
    log_metrics,
    save_weekly_strategy,
)
from tools.memory import (
    MEMORY_TOOL_DEFINITIONS,
    search_similar_venues_tool,
    search_similar_outreach_tool,
    search_similar_posts_tool,
    search_past_strategies_tool,
)
from agents.model_router import TaskTier, classify_intent, route

# ---------------------------------------------------------------------------
# Specialised agent personas
# ---------------------------------------------------------------------------

_BOOKING_PERSONA = """You are the Booking Agent for {artist_name}.
Your sole focus is securing live performance opportunities.
You research venues, draft compelling booking emails, and track the outreach pipeline.
Always be professional, persistent, and strategic. Aim for 5–10 gigs by summer.
Weekly target: contact 5–10 new venues and follow up on any overdue conversations."""

_CONTENT_PERSONA = """You are the Social Media & Content Agent for {artist_name}.
Your sole focus is growing the artist's online presence and listener count.
You create engaging, platform-appropriate content and build repost networks.
Targets: 300 monthly listeners by mid-year, 1,000 by end of year.
Strategies: monthly DJ mixes, short-form video content, repost network outreach."""

_STRATEGY_PERSONA = """You are the Strategy & Analytics Agent for {artist_name}.
Your sole focus is high-level planning and performance analysis.
You generate weekly strategies, analyse growth trends, and recommend tactical pivots.
Always ground recommendations in data and align with the artist's stated goals."""

_ORCHESTRATOR_PERSONA = """You are the AI Artist Manager for {artist_name}, a {artist_genre} DJ/producer based in {artist_location}.

ARTIST PROFILE:
- Name: {artist_name}
- Genre: {artist_genre}
- Location: {artist_location}
- Bio: {artist_bio}

GOALS:
- Book 5–10 gigs by summer (weekly target: contact 5–10 promoters, send follow-ups)
- Reach 300 monthly listeners by mid-year, 1,000 by end of year
- Maintain consistent social presence across Instagram, SoundCloud, Mixcloud

CAPABILITIES:
You have tools to manage venues, track outreach, generate social content,
log metrics, and produce weekly strategies. You coordinate a team of
specialised agents: Booking, Content, and Strategy.

Be proactive, concise, and action-oriented. When a user mentions a task,
execute it — don't just describe what you'd do."""


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

ALL_TOOLS = (
    BOOKING_TOOL_DEFINITIONS
    + OUTREACH_TOOL_DEFINITIONS
    + SOCIAL_TOOL_DEFINITIONS
    + METRICS_TOOL_DEFINITIONS
    + MEMORY_TOOL_DEFINITIONS
)

# Subset maps for specialised agents — each gets relevant memory search tools
BOOKING_TOOLS = (
    BOOKING_TOOL_DEFINITIONS
    + OUTREACH_TOOL_DEFINITIONS
    + [t for t in MEMORY_TOOL_DEFINITIONS if t["name"] in ("search_similar_venues", "search_similar_outreach")]
)
CONTENT_TOOLS = (
    SOCIAL_TOOL_DEFINITIONS
    + [t for t in MEMORY_TOOL_DEFINITIONS if t["name"] == "search_similar_posts"]
)
STRATEGY_TOOLS = (
    METRICS_TOOL_DEFINITIONS
    + OUTREACH_TOOL_DEFINITIONS
    + [t for t in MEMORY_TOOL_DEFINITIONS if t["name"] in ("search_past_strategies", "search_similar_outreach")]
)


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """Route tool calls to their Python implementations."""
    with db_session() as db:
        handlers = {
            # Booking
            "add_venue": lambda i: add_venue(db, **i),
            "search_venues": lambda i: search_venues(db, **i),
            "draft_booking_email": lambda i: draft_booking_email(db, **i),
            # Outreach
            "record_outreach": lambda i: record_outreach(db, **i),
            "update_outreach": lambda i: update_outreach(db, **i),
            "get_outreach_pipeline": lambda i: get_outreach_pipeline(db, **i),
            "get_follow_up_reminders": lambda i: get_follow_up_reminders(db, **i),
            # Social
            "save_social_post": lambda i: save_social_post(db, **i),
            "get_recent_posts": lambda i: get_recent_posts(db, **i),
            "generate_content_brief": lambda i: generate_content_brief(db, **i),
            # Metrics
            "log_metrics": lambda i: log_metrics(db, **i),
            "get_metrics_history": lambda i: get_metrics_history(db, **i),
            "get_progress_report": lambda i: get_progress_report(db, **i),
            "save_weekly_strategy": lambda i: save_weekly_strategy(db, **i),
            "get_recent_strategies": lambda i: get_recent_strategies(db, **i),
            # Vector memory search (no DB session needed)
            "search_similar_venues": lambda i: search_similar_venues_tool(**i),
            "search_similar_outreach": lambda i: search_similar_outreach_tool(**i),
            "search_similar_posts": lambda i: search_similar_posts_tool(**i),
            "search_past_strategies": lambda i: search_past_strategies_tool(**i),
        }
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            return handler(tool_input)
        except TypeError as e:
            return json.dumps({"error": f"Invalid tool arguments for {tool_name}: {e}"})
        except Exception as e:
            return json.dumps({"error": f"Tool {tool_name} failed: {e}"})


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------


class ArtistManagerAgent:
    """
    Orchestrates specialised agents using Claude with tool use.
    Streams token-by-token and yields text chunks.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.conversation: list[dict] = []

    def _build_system_prompt(self, persona_template: str) -> str:
        s = self.settings
        return persona_template.format(
            artist_name=s.artist_name,
            artist_genre=s.artist_genre,
            artist_location=s.artist_location,
            artist_bio=s.artist_bio,
        )

    def _pick_agent_config(self, user_message: str) -> tuple[str, list, TaskTier]:
        """
        Route to the appropriate specialised agent based on intent.
        Returns (system_prompt, tools, tier).
        """
        msg = user_message.lower()

        booking_keywords = [
            "book", "gig", "venue", "promoter", "email", "outreach",
            "pipeline", "follow-up", "follow up", "contact",
        ]
        content_keywords = [
            "instagram", "post", "social", "content", "caption", "hashtag",
            "soundcloud", "mixcloud", "tiktok", "mix", "release", "announce",
        ]
        strategy_keywords = [
            "strategy", "plan", "report", "progress", "metrics", "listeners",
            "growth", "weekly", "goals", "analyse", "analyze",
        ]

        booking_score = sum(1 for kw in booking_keywords if kw in msg)
        content_score = sum(1 for kw in content_keywords if kw in msg)
        strategy_score = sum(1 for kw in strategy_keywords if kw in msg)

        tier = classify_intent(user_message)

        if booking_score >= content_score and booking_score >= strategy_score:
            system = self._build_system_prompt(_BOOKING_PERSONA)
            tools = BOOKING_TOOLS
        elif content_score >= strategy_score:
            system = self._build_system_prompt(_CONTENT_PERSONA)
            tools = CONTENT_TOOLS
        elif strategy_score > 0:
            system = self._build_system_prompt(_STRATEGY_PERSONA)
            tools = STRATEGY_TOOLS
        else:
            # Default to orchestrator with all tools
            system = self._build_system_prompt(_ORCHESTRATOR_PERSONA)
            tools = ALL_TOOLS

        return system, tools, tier

    def chat_stream(self, user_message: str) -> Iterator[str]:
        """
        Send a message and stream the response token by token.
        Handles the full tool-use agentic loop.
        Yields text chunks as they arrive.
        """
        self.conversation.append({"role": "user", "content": user_message})

        system_prompt, tools, tier = self._pick_agent_config(user_message)
        model_cfg = route(tier)

        while True:
            create_kwargs = {
                **model_cfg,
                "system": system_prompt,
                "tools": tools,
                "messages": self.conversation,
            }

            full_content = []
            current_tool_calls = []
            yielded_text = []

            with self.client.messages.stream(**create_kwargs) as stream:
                current_block_type = None
                current_block_index = None
                current_json_parts = {}

                for event in stream:
                    if event.type == "content_block_start":
                        blk = event.content_block
                        current_block_type = blk.type
                        current_block_index = event.index
                        if blk.type == "tool_use":
                            current_tool_calls.append({
                                "type": "tool_use",
                                "id": blk.id,
                                "name": blk.name,
                                "input": {},
                            })
                            current_json_parts[event.index] = ""

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yielded_text.append(delta.text)
                            yield delta.text
                        elif delta.type == "input_json_delta":
                            if event.index in current_json_parts:
                                current_json_parts[event.index] += delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_block_type == "tool_use" and event.index in current_json_parts:
                            raw = current_json_parts.pop(event.index)
                            for tc in current_tool_calls:
                                if not tc["input"]:  # not yet populated
                                    try:
                                        tc["input"] = json.loads(raw) if raw else {}
                                    except json.JSONDecodeError:
                                        tc["input"] = {}
                                    break

                final_msg = stream.get_final_message()

            stop_reason = final_msg.stop_reason
            full_content = final_msg.content

            # Append assistant message to conversation history
            self.conversation.append({"role": "assistant", "content": full_content})

            if stop_reason == "end_turn" or not current_tool_calls:
                break

            # Execute tool calls and feed results back
            tool_results = []
            for tc in current_tool_calls:
                result = _execute_tool(tc["name"], tc["input"])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": result,
                })

            self.conversation.append({"role": "user", "content": tool_results})
            # Loop continues — Claude will process results and respond

    def chat(self, user_message: str) -> str:
        """Non-streaming version — returns the complete response."""
        return "".join(self.chat_stream(user_message))

    def reset(self):
        """Clear conversation history."""
        self.conversation = []
