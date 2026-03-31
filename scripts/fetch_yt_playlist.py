#!/usr/bin/env python3
"""
Fetch all videos from a YouTube channel and build a central playlist JSON.

Usage:
    python scripts/fetch_yt_playlist.py https://www.youtube.com/@FreeisinDaHouse
    python scripts/fetch_yt_playlist.py https://www.youtube.com/@FreeisinDaHouse --output data/playlist.json

Requires: pip install yt-dlp
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def fetch_channel_videos(channel_url: str) -> list[dict]:
    """Use yt-dlp to extract all video metadata from a YouTube channel."""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        f"{channel_url}/videos",
    ]
    print(f"Fetching videos from {channel_url} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

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

    return videos


def build_playlist(channel_url: str, videos: list[dict]) -> dict:
    """Structure videos into a playlist document."""
    return {
        "playlist_name": "Free is in Da House — Complete Collection",
        "source_channel": channel_url,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "total_tracks": len(videos),
        "tracks": videos,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube channel into a playlist JSON")
    parser.add_argument("channel_url", help="YouTube channel URL (e.g. https://www.youtube.com/@FreeisinDaHouse)")
    parser.add_argument("--output", "-o", default="data/playlist.json", help="Output JSON path")
    args = parser.parse_args()

    videos = fetch_channel_videos(args.channel_url)

    if not videos:
        print("No videos found. Check the channel URL.", file=sys.stderr)
        sys.exit(1)

    playlist = build_playlist(args.channel_url, videos)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(playlist, indent=2, ensure_ascii=False))

    print(f"\nPlaylist saved to {output_path}")
    print(f"Total tracks: {playlist['total_tracks']}")
    print("\nFirst 10 tracks:")
    for i, track in enumerate(videos[:10], 1):
        print(f"  {i}. {track['title']}")
    if len(videos) > 10:
        print(f"  ... and {len(videos) - 10} more")


if __name__ == "__main__":
    main()
