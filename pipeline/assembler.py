"""
pipeline/assembler.py
Combines stock footage + voiceover + subtitles into a final MP4.
Uses MoviePy 1.0.3.

Subtitles require ImageMagick:
  macOS:   brew install imagemagick
  Ubuntu:  sudo apt install imagemagick
  Windows: https://imagemagick.org/script/download.php
If ImageMagick is missing, subtitles are automatically skipped.
"""

import os
import math
import numpy as np

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
    ImageClip,
)
from moviepy.audio.fx.all import audio_fadein, audio_fadeout

# ── Constants ──────────────────────────────────────────────────────────────────

TARGET_W = 1920
TARGET_H = 1080
FPS = 30
SUBTITLE_FONTSIZE = 52
SUBTITLE_FONT = "Arial-Bold"
SUBTITLE_COLOR = "white"
SUBTITLE_STROKE = "black"
SUBTITLE_STROKE_W = 2
SUBTITLE_Y_OFFSET = 120   # pixels from bottom

# Background colour when no footage is available
BG_COLOR = (15, 15, 35)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _resize_and_crop(clip, w: int, h: int):
    """Scale clip to fill (w × h) then centre-crop — no black bars."""
    clip_ratio = clip.w / clip.h
    target_ratio = w / h

    if clip_ratio > target_ratio:
        # Clip is wider → fit height, crop sides
        clip = clip.resize(height=h)
    else:
        # Clip is taller → fit width, crop top/bottom
        clip = clip.resize(width=w)

    return clip.crop(
        x_center=clip.w / 2,
        y_center=clip.h / 2,
        width=w,
        height=h,
    )


def _loop_to_duration(clip, duration: float):
    """Loop a clip until it reaches `duration` seconds."""
    loops = math.ceil(duration / clip.duration)
    looped = concatenate_videoclips([clip] * loops)
    return looped.subclip(0, duration)


def _make_subtitle(text: str, duration: float, w: int, h: int):
    """Return a TextClip positioned at the bottom, or None if unavailable."""
    try:
        txt = (
            TextClip(
                text,
                fontsize=SUBTITLE_FONTSIZE,
                font=SUBTITLE_FONT,
                color=SUBTITLE_COLOR,
                stroke_color=SUBTITLE_STROKE,
                stroke_width=SUBTITLE_STROKE_W,
                method="caption",
                size=(w - 120, None),
                align="center",
            )
            .set_duration(duration)
            .set_position(("center", h - SUBTITLE_Y_OFFSET - 20))
        )
        return txt
    except Exception as exc:
        # ImageMagick probably missing
        print(f"          ⚠  Subtitles unavailable ({exc}). Install ImageMagick to enable.")
        return None


# ── Subtitle word-chunking ─────────────────────────────────────────────────────


def _chunk_text(text: str, audio_duration: float, words_per_chunk: int = 7):
    """
    Split text into timed subtitle chunks.
    Returns list of (chunk_text, start_sec, end_sec).
    """
    words = text.split()
    if not words:
        return []

    chunks = [words[i : i + words_per_chunk] for i in range(0, len(words), words_per_chunk)]
    seconds_per_word = audio_duration / len(words)
    results = []
    t = 0.0

    for chunk in chunks:
        chunk_text = " ".join(chunk)
        chunk_dur = len(chunk) * seconds_per_word
        results.append((chunk_text, t, t + chunk_dur))
        t += chunk_dur

    return results


# ── Main assembler ─────────────────────────────────────────────────────────────


def assemble_video(
    footage_files: list,
    audio_files: list,
    segments: list,
    output_path: str,
    video_width: int = TARGET_W,
    video_height: int = TARGET_H,
    fps: int = FPS,
    add_subtitles: bool = True,
) -> str:
    """
    Build the final video from per-segment footage + audio.
    Returns the path to the exported MP4.
    """
    final_clips = []
    subtitle_ok = add_subtitles  # will be set False if TextClip fails once

    for i, (footage_path, audio_path, segment) in enumerate(
        zip(footage_files, audio_files, segments)
    ):
        print(f"     [{i + 1}/{len(segments)}] Compositing segment…")

        # ── Audio ────────────────────────────────────────────────────────────
        audio = AudioFileClip(audio_path)
        seg_dur = audio.duration

        # ── Video base ───────────────────────────────────────────────────────
        if footage_path and os.path.exists(footage_path):
            try:
                raw = VideoFileClip(footage_path, audio=False)
                if raw.duration < seg_dur:
                    raw = _loop_to_duration(raw, seg_dur)
                else:
                    raw = raw.subclip(0, seg_dur)
                base = _resize_and_crop(raw, video_width, video_height)
            except Exception as exc:
                print(f"          ⚠  Could not load footage ({exc}) — using colour bg")
                base = ColorClip((video_width, video_height), color=BG_COLOR, duration=seg_dur)
        else:
            base = ColorClip((video_width, video_height), color=BG_COLOR, duration=seg_dur)

        base = base.set_audio(audio)

        # ── Subtitles ────────────────────────────────────────────────────────
        if subtitle_ok:
            chunks = _chunk_text(segment["text"], seg_dur)
            sub_clips = []
            for chunk_text, t_start, t_end in chunks:
                sub = _make_subtitle(
                    chunk_text, t_end - t_start, video_width, video_height
                )
                if sub is None:
                    subtitle_ok = False  # disable for rest of video
                    break
                sub_clips.append(sub.set_start(t_start))

            if sub_clips:
                base = CompositeVideoClip([base] + sub_clips)

        base = base.set_duration(seg_dur)
        final_clips.append(base)

    # ── Concatenate ──────────────────────────────────────────────────────────
    print("     🔗  Concatenating all segments…")
    final = concatenate_videoclips(final_clips, method="compose")

    # ── Export ───────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    temp_audio = os.path.join("temp", "temp_audio_export.m4a")

    print(f"     💾  Writing {output_path} …")
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=temp_audio,
        remove_temp=True,
        preset="fast",      # fast | medium | slow  (speed vs file size)
        logger="bar",
    )

    # Clean up
    for clip in final_clips:
        clip.close()
    final.close()

    return output_path
