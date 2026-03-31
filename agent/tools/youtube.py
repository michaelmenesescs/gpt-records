"""
YouTube channel tools: fetch videos and build playlists.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# ---------------------------------------------------------------------------
# Tool definitions (exposed to the AI agent)
# ---------------------------------------------------------------------------

YOUTUBE_TOOL_DEFINITIONS = [
    {
        "name": "fetch_channel_playlist",
        "description": (
            "Fetch all videos from a YouTube channel and save as a central playlist. "
            "Requires yt-dlp installed. Returns the playlist summary and file path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_url": {
                    "type": "string",
                    "description": "YouTube channel URL, e.g. 'https://www.youtube.com/@FreeisinDaHouse'",
                },
                "playlist_name": {
                    "type": "string",
                    "description": "Custom name for the playlist (optional)",
                },
            },
            "required": ["channel_url"],
        },
    },
    {
        "name": "get_playlist",
        "description": (
            "Load and return the current saved playlist. "
            "Optionally search/filter tracks by keyword."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Filter tracks whose title contains this keyword",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max tracks to return (default 50)",
                },
            },
        },
    },
    {
        "name": "export_playlist_urls",
        "description": (
            "Export all playlist track URLs as a plain text file, "
            "one URL per line — ready to import into YouTube, VLC, or other players."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "output_format": {
                    "type": "string",
                    "enum": ["urls", "m3u"],
                    "description": "Output format: 'urls' (plain list) or 'm3u' (playlist file)",
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def fetch_channel_playlist(
    channel_url: str,
    playlist_name: Optional[str] = None,
) -> str:
    """Fetch all videos from a YouTube channel using yt-dlp."""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        f"{channel_url}/videos",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return json.dumps({"error": "yt-dlp is not installed. Run: pip install yt-dlp"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Timed out fetching channel. The channel may have too many videos."})

    if result.returncode != 0:
        return json.dumps({"error": f"yt-dlp failed: {result.stderr[:500]}"})

    videos = []
    for line in result.stdout.strip().splitlines():
        try:
            entry = json.loads(line)
            videos.append({
                "title": entry.get("title", "Unknown"),
                "video_id": entry.get("id", ""),
                "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                "duration": entry.get("duration"),
                "upload_date": entry.get("upload_date"),
                "view_count": entry.get("view_count"),
                "channel": entry.get("channel") or entry.get("uploader", ""),
            })
        except json.JSONDecodeError:
            continue

    if not videos:
        return json.dumps({"error": "No videos found. Check the channel URL."})

    default_name = f"YouTube Channel Playlist"
    playlist = {
        "playlist_name": playlist_name or default_name,
        "source_channel": channel_url,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "total_tracks": len(videos),
        "tracks": videos,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "playlist.json"
    output_path.write_text(json.dumps(playlist, indent=2, ensure_ascii=False))

    return json.dumps({
        "status": "success",
        "playlist_name": playlist["playlist_name"],
        "total_tracks": len(videos),
        "file": str(output_path),
        "sample_tracks": [t["title"] for t in videos[:10]],
    })


def get_playlist(
    search: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Load the saved playlist, optionally filtering by keyword."""
    playlist_path = DATA_DIR / "playlist.json"
    if not playlist_path.exists():
        return json.dumps({"error": "No playlist found. Run fetch_channel_playlist first."})

    playlist = json.loads(playlist_path.read_text())
    tracks = playlist["tracks"]

    if search:
        keyword = search.lower()
        tracks = [t for t in tracks if keyword in t["title"].lower()]

    return json.dumps({
        "playlist_name": playlist["playlist_name"],
        "source_channel": playlist["source_channel"],
        "fetched_at": playlist["fetched_at"],
        "total_tracks": playlist["total_tracks"],
        "showing": len(tracks[:limit]),
        "tracks": tracks[:limit],
    })


def export_playlist_urls(
    output_format: str = "urls",
) -> str:
    """Export playlist as a URL list or M3U file."""
    playlist_path = DATA_DIR / "playlist.json"
    if not playlist_path.exists():
        return json.dumps({"error": "No playlist found. Run fetch_channel_playlist first."})

    playlist = json.loads(playlist_path.read_text())
    tracks = playlist["tracks"]

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if output_format == "m3u":
        lines = ["#EXTM3U", f"#PLAYLIST:{playlist['playlist_name']}"]
        for t in tracks:
            duration = t.get("duration") or -1
            lines.append(f"#EXTINF:{duration},{t['title']}")
            lines.append(t["url"])
        out_file = DATA_DIR / "playlist.m3u"
        out_file.write_text("\n".join(lines) + "\n")
    else:
        lines = [t["url"] for t in tracks]
        out_file = DATA_DIR / "playlist_urls.txt"
        out_file.write_text("\n".join(lines) + "\n")

    return json.dumps({
        "status": "exported",
        "format": output_format,
        "file": str(out_file),
        "track_count": len(tracks),
    })
