"""
Interactive CLI for the AI Artist Manager.

Usage:
    python -m agent          # Start interactive session
    python -m agent migrate  # Create database tables
    python -m agent demo     # Load demo data
"""
import sys
import os

# Ensure the agent directory is on the path when run as a module
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.rule import Rule

from config import get_settings
from db.session import init_db
from agents.manager import ArtistManagerAgent

console = Console()


BANNER = """
[bold cyan]╔══════════════════════════════════════════════╗
║      GPT Records — AI Artist Manager         ║
║      Booking · Social · Strategy · Analytics ║
╚══════════════════════════════════════════════╝[/bold cyan]
"""

HELP_TEXT = """
**Commands:**
- Type any message to talk to your AI manager
- `reset` — clear conversation history
- `demo`  — load sample venues and metrics
- `help`  — show this help
- `quit` / `exit` / Ctrl+C — exit

**Example prompts:**
- "What gigs should I be targeting this week?"
- "Draft a booking email for Fabric in London"
- "Generate this week's Instagram content"
- "Show me my outreach pipeline"
- "Generate a weekly strategy"
- "Log my current metrics: 150 monthly listeners, 420 SoundCloud followers"
"""


def load_demo_data():
    """Insert sample venues and a metric entry for demonstration."""
    from db.session import db_session
    from tools.booking import add_venue
    from tools.metrics import log_metrics

    sample_venues = [
        {
            "name": "Fabric",
            "city": "London",
            "country": "UK",
            "contact_email": "bookings@fabriclondon.com",
            "genres": "techno, house, electronic",
            "capacity": 2500,
            "notes": "Prestigious London club. Long application lead time.",
        },
        {
            "name": "Corsica Studios",
            "city": "London",
            "country": "UK",
            "contact_email": "bookings@corsicastudios.com",
            "genres": "techno, experimental, electronic",
            "capacity": 600,
            "notes": "Underground venue, good for emerging artists.",
        },
        {
            "name": "Tresor",
            "city": "Berlin",
            "country": "Germany",
            "contact_email": "booking@tresorberlin.com",
            "genres": "techno, industrial",
            "capacity": 1500,
            "notes": "Iconic Berlin techno club.",
        },
        {
            "name": "Fold",
            "city": "London",
            "country": "UK",
            "contact_email": "bookings@fold.london",
            "genres": "techno, rave, electronic",
            "capacity": 800,
            "notes": "Newer East London venue with strong community.",
        },
        {
            "name": "Junction 2",
            "city": "London",
            "country": "UK",
            "contact_email": "info@junction2festival.com",
            "genres": "techno, house, electronic",
            "capacity": 5000,
            "notes": "Annual festival under Hammersmith flyover.",
        },
    ]

    with db_session() as db:
        for v in sample_venues:
            add_venue(db, **v)
        log_metrics(
            db,
            monthly_listeners=85,
            soundcloud_followers=312,
            instagram_followers=890,
            mixcloud_followers=145,
            notes="Demo baseline metrics",
        )

    console.print("[green]✓ Demo data loaded: 5 venues + baseline metrics[/green]")


def run_cli():
    settings = get_settings()
    init_db()

    console.print(BANNER)
    console.print(
        f"[dim]Artist:[/dim] [bold]{settings.artist_name}[/bold]  "
        f"[dim]Genre:[/dim] {settings.artist_genre}  "
        f"[dim]Location:[/dim] {settings.artist_location}"
    )
    console.print(f"[dim]Model:[/dim] claude-opus-4-6 (adaptive routing)")
    console.print(Rule(style="dim"))
    console.print(Markdown(HELP_TEXT))
    console.print(Rule(style="dim"))

    agent = ArtistManagerAgent(settings)

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if lower == "reset":
            agent.reset()
            console.print("[yellow]Conversation history cleared.[/yellow]")
            continue

        if lower == "help":
            console.print(Markdown(HELP_TEXT))
            continue

        if lower == "demo":
            load_demo_data()
            continue

        if lower == "migrate":
            init_db()
            console.print("[green]Database tables ensured.[/green]")
            continue

        console.print(f"\n[bold cyan]Manager[/bold cyan]", end=" ")

        try:
            buffer = []
            for chunk in agent.chat_stream(user_input):
                console.print(chunk, end="", markup=False)
                buffer.append(chunk)
            console.print()  # newline after stream
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


def run_migrate():
    init_db()
    console.print("[green]Database tables created.[/green]")


def run_demo():
    init_db()
    load_demo_data()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "cli"
    if cmd == "migrate":
        run_migrate()
    elif cmd == "demo":
        run_demo()
    else:
        run_cli()
