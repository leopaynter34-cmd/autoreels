"""
pipeline/tts.py
Generates voiceover audio for each script segment using OpenAI TTS.
"""

import os
from pathlib import Path
from openai import OpenAI

client = OpenAI()

# Available voices: alloy, echo, fable, onyx, nova, shimmer
DEFAULT_VOICE = "alloy"


def generate_voiceover(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> str:
    """
    Convert text → MP3 audio file using OpenAI TTS.
    Returns the output path.
    """
    response = client.audio.speech.create(
        model="tts-1",   # tts-1-hd for higher quality (slower, costs more)
        voice=voice,
        input=text,
        speed=1.0,       # 0.25–4.0  (1.0 = natural pace)
    )

    Path(output_path).write_bytes(response.content)
    return output_path


def generate_segment_audio(
    segments: list, temp_dir: str, voice: str = DEFAULT_VOICE
) -> list[str]:
    """
    Generate one MP3 per script segment.
    Returns a list of audio file paths in order.
    """
    audio_files = []

    for i, segment in enumerate(segments):
        audio_path = os.path.join(temp_dir, f"audio_{i:03d}.mp3")
        generate_voiceover(segment["text"], audio_path, voice)
        audio_files.append(audio_path)
        print(f"     ✓ Audio {i + 1}/{len(segments)}")

    return audio_files
