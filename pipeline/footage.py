"""
pipeline/footage.py
Searches Pexels for stock footage and downloads the best match per segment.
Pexels API is free — get a key at https://www.pexels.com/api/
"""

import os
import random
import requests

PEXELS_API = "https://api.pexels.com/videos"
FALLBACK_QUERIES = ["nature landscape", "city timelapse", "abstract background"]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _search(query: str, api_key: str, per_page: int = 10) -> list:
    """Return a list of Pexels video objects matching the query."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
        "size": "medium",          # small | medium | large
    }
    resp = requests.get(f"{PEXELS_API}/search", headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("videos", [])


def _best_file(video: dict, min_width: int = 1280) -> dict | None:
    """Pick the highest-resolution MP4 file from a Pexels video object."""
    files = video.get("video_files", [])
    mp4s = [f for f in files if f.get("file_type") == "video/mp4"]

    hd = [f for f in mp4s if f.get("width", 0) >= min_width]
    pool = hd if hd else mp4s
    if not pool:
        return None

    return max(pool, key=lambda f: f.get("width", 0))


def _download(url: str, dest: str) -> str:
    """Stream-download a file to dest."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=16_384):
            fh.write(chunk)
    return dest


# ── Public API ────────────────────────────────────────────────────────────────


def fetch_footage_for_segments(
    segments: list, api_key: str, temp_dir: str
) -> list[str | None]:
    """
    For each segment, search Pexels using its keywords and download one clip.
    Returns a list of local file paths (None if a clip couldn't be found).
    """
    footage_paths = []

    for i, segment in enumerate(segments):
        keywords = segment.get("keywords", [])
        query = " ".join(keywords[:2]) if keywords else "nature"

        print(f"     🔍  [{i + 1}/{len(segments)}] Searching: '{query}'")

        videos = _search(query, api_key)

        # Fallback: try first keyword only
        if not videos and keywords:
            videos = _search(keywords[0], api_key)

        # Fallback: generic query
        if not videos:
            fallback = random.choice(FALLBACK_QUERIES)
            print(f"          ↳ No results — falling back to '{fallback}'")
            videos = _search(fallback, api_key)

        path = None
        if videos:
            # Pick randomly from the top 5 for variety
            video = random.choice(videos[:5])
            vfile = _best_file(video)
            if vfile:
                dest = os.path.join(temp_dir, f"footage_{i:03d}.mp4")
                _download(vfile["link"], dest)
                path = dest
                print(f"          ✓ Downloaded")
            else:
                print(f"          ⚠  No suitable file found — will use colour background")
        else:
            print(f"          ⚠  No footage found — will use colour background")

        footage_paths.append(path)

    return footage_paths
