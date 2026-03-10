"""
Model router — selects the right Claude model based on task complexity.

Architecture:
  High-stakes tasks (strategy, complex drafting)  → claude-opus-4-6  (adaptive thinking)
  Standard tasks (email drafts, content)           → claude-opus-4-6
  Simple/fast tasks (classification, lookups)      → claude-haiku-4-5
"""
from enum import Enum


class TaskTier(str, Enum):
    """Complexity tiers that map to model selection."""
    HEAVY = "heavy"    # Deep reasoning: strategy, analysis
    STANDARD = "standard"  # Most tasks: drafting, planning
    FAST = "fast"      # Quick tasks: classification, summaries


# Map tiers to model IDs
MODEL_MAP = {
    TaskTier.HEAVY: "claude-opus-4-6",
    TaskTier.STANDARD: "claude-opus-4-6",
    TaskTier.FAST: "claude-haiku-4-5",
}

# Thinking config per tier
THINKING_MAP = {
    TaskTier.HEAVY: {"type": "adaptive"},
    TaskTier.STANDARD: None,
    TaskTier.FAST: None,
}

# Max tokens per tier
MAX_TOKENS_MAP = {
    TaskTier.HEAVY: 8192,
    TaskTier.STANDARD: 4096,
    TaskTier.FAST: 1024,
}


def route(tier: TaskTier) -> dict:
    """Return kwargs to pass to client.messages.create / stream."""
    cfg = {
        "model": MODEL_MAP[tier],
        "max_tokens": MAX_TOKENS_MAP[tier],
    }
    thinking = THINKING_MAP[tier]
    if thinking:
        cfg["thinking"] = thinking
    return cfg


def classify_intent(user_message: str) -> TaskTier:
    """
    Simple keyword-based intent classification.
    Returns the appropriate tier so the orchestrator can pick the right model.
    """
    msg = user_message.lower()

    heavy_keywords = [
        "strategy", "plan", "analyse", "analyze", "report", "progress",
        "roadmap", "quarterly", "annual", "recommend", "assess", "evaluate",
    ]
    fast_keywords = [
        "list", "show", "get", "fetch", "how many", "status", "remind",
        "what is", "find", "search",
    ]

    if any(kw in msg for kw in heavy_keywords):
        return TaskTier.HEAVY
    if any(kw in msg for kw in fast_keywords):
        return TaskTier.FAST
    return TaskTier.STANDARD
