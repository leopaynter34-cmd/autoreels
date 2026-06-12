#!/usr/bin/env python3
"""
AI YouTube Video Generator
Topic in → Full YouTube video out.
"""

import os
import sys
import shutil
import argparse
from dotenv import load_dotenv

load_dotenv()

from pipeline.script import generate_script
from pipeline.tts import generate_segment_audio
from pipeline.footage import fetch_footage_for_segments
from pipeline.assembler import assemble_video

TEMP_DIR = "temp"
OUTPUT_DIR = "output"


def setup_dirs():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def cleanup_temp():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)


def check_env():
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("PEXELS_API_KEY"):
        missing.append("PEXELS_API_KEY")
    if missing:
        print(f"❌ Missing API keys in .env: {', '.join(missing)}")
        print("   Copy .env.example → .env and fill in your keys.")
        sys.exit(1)


def generate_video(
    topic: str,
    duration: int = 60,
    style: str = "informative",
    voice: str = "alloy",
    add_subtitles: bool = True,
):
    """Full pipeline: topic → YouTube-ready MP4."""
    check_env()
    setup_dirs()
    cleanup_temp()

    print(f"\n🚀  Generating video: '{topic}'")
    print("=" * 55)

    # ── Step 1: Script ──────────────────────────────────────────
    print("\n📝  Step 1/4 — Generating script with GPT-4o…")
    script = generate_script(topic, duration=duration, style=style)
    print(f"     Title    : {script['title']}")
    print(f"     Segments : {len(script['segments'])}")

    # ── Step 2: Voiceover ───────────────────────────────────────
    print("\n🎙   Step 2/4 — Generating voiceover (OpenAI TTS)…")
    audio_files = generate_segment_audio(script["segments"], TEMP_DIR, voice=voice)

    # ── Step 3: Stock footage ───────────────────────────────────
    print("\n🎥  Step 3/4 — Fetching stock footage from Pexels…")
    footage_files = fetch_footage_for_segments(
        script["segments"], os.getenv("PEXELS_API_KEY"), TEMP_DIR
    )

    # ── Step 4: Assemble ────────────────────────────────────────
    print("\n🎬  Step 4/4 — Assembling final video…")
    safe_title = (
        "".join(c for c in script["title"] if c.isalnum() or c in " -_")
        .strip()
        .replace(" ", "_")[:50]
    )
    output_path = os.path.join(OUTPUT_DIR, f"{safe_title}.mp4")

    assemble_video(
        footage_files=footage_files,
        audio_files=audio_files,
        segments=script["segments"],
        output_path=output_path,
        add_subtitles=add_subtitles,
    )

    # ── Done ────────────────────────────────────────────────────
    print("\n✅  Video ready!")
    print(f"   📁 File  : {output_path}")
    print(f"   📌 Title : {script['title']}")
    print(f"\n   📋 Description:\n{script['description']}")
    print(f"\n   🏷   Tags: {', '.join(script['tags'])}")

    return output_path, script


def main():
    parser = argparse.ArgumentParser(
        description="AI YouTube Video Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("topic", help='Video topic, e.g. "5 facts about black holes"')
    parser.add_argument(
        "--duration", type=int, default=60, help="Target length in seconds"
    )
    parser.add_argument(
        "--style",
        default="informative",
        choices=["informative", "listicle", "storytelling", "educational"],
    )
    parser.add_argument(
        "--voice",
        default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="OpenAI TTS voice",
    )
    parser.add_argument(
        "--no-subtitles", action="store_true", help="Disable burnt-in subtitles"
    )
    args = parser.parse_args()

    generate_video(
        topic=args.topic,
        duration=args.duration,
        style=args.style,
        voice=args.voice,
        add_subtitles=not args.no_subtitles,
    )


if __name__ == "__main__":
    main()
