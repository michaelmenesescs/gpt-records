# GPT Records — AI Artist Manager

Local AI agent platform for music promotion and booking, powered by Claude Opus 4.6.

## Architecture

```
Frontend Dashboard (future)
        │
        ▼
Agent API (FastAPI :8000)
        │
        ▼
Agent Orchestrator
        │
 ┌──────┼──────────┐
 │      │          │
Booking  Content  Strategy
Agent    Agent    Agent
        │
        ▼
Model Router
  Opus 4.6  (strategy, complex drafts)
  Haiku 4.5 (fast lookups)
        │
        ▼
Storage Layer (PostgreSQL)
  venues · outreach_records
  social_posts · metric_entries
  weekly_strategies
```

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and your artist details
```

### 2. Start services

```bash
make up          # starts PostgreSQL + API
make logs        # tail logs
```

### 3. Interactive CLI

```bash
make cli         # opens the interactive manager inside Docker
# or locally:
make cli-local
```

### 4. Load demo data

```
> demo           # inside the CLI
```

## Example Conversations

```
You: Draft a booking email for Corsica Studios in London

You: Show me my outreach pipeline

You: Generate this week's Instagram content for a new mix release

You: Log my metrics: 150 monthly listeners, 420 SoundCloud followers

You: Generate a weekly strategy — check the pipeline first

You: Fabric just replied positively! Update outreach ID 3 to responded_positive
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Streaming SSE chat |
| POST | `/api/chat/sync` | Blocking chat |
| GET | `/api/pipeline` | Outreach pipeline |
| POST | `/api/pipeline` | Log new outreach |
| PATCH | `/api/pipeline/{id}` | Update outreach status |
| GET | `/api/reminders` | Overdue follow-ups |
| GET | `/api/venues` | Search venues |
| POST | `/api/venues` | Add venue |
| GET | `/api/metrics` | Metrics history |
| POST | `/api/metrics` | Log metrics snapshot |
| GET | `/api/strategies` | Recent strategies |
| POST | `/api/strategies/generate` | AI-generate weekly strategy |
| GET | `/health` | Liveness check |

## Goals

| Goal | Target |
|------|--------|
| Gigs booked | 5–10 by summer |
| Weekly outreach | 5–10 promoters/venues |
| Monthly listeners (mid-year) | 300 |
| Monthly listeners (end of year) | 1,000 |

## Remote Access via Tailscale

With Tailscale installed on your Mac Mini M4:
1. Start the stack: `make up`
2. Access from any device on your Tailnet: `http://<mac-mini-tailscale-ip>:8000`

## Development

```bash
make build       # rebuild Docker image
make shell       # bash inside the agent container
make db-shell    # psql session
make migrate     # create/update DB tables
```
