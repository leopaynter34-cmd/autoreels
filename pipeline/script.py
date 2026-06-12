"""
pipeline/script.py
Generates a structured YouTube video script using GPT-4o.
"""

import os
import json
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from env

SCRIPT_PROMPT = """
You are an expert YouTube scriptwriter. Write an engaging video script.

Topic    : {topic}
Duration : ~{duration} seconds (~{word_count} words total)
Style    : {style}

Return ONLY a valid JSON object — no markdown, no preamble — with this exact structure:
{{
  "title": "Catchy YouTube video title (under 70 characters)",
  "description": "YouTube description (150-200 words, SEO-optimised, include timestamps)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "segments": [
    {{
      "text": "Narration text spoken in this segment (1-3 sentences).",
      "keywords": ["stock footage keyword 1", "stock footage keyword 2"],
      "duration": 10
    }}
  ]
}}

Rules:
- Each segment = 8-15 seconds of narration (match the word count).
- keywords describe the VISUAL: what stock footage to show. Be specific:
  "busy city street night", "scientist looking microscope", "ocean waves sunset".
- Together all segment durations should sum to roughly {duration} seconds.
- Hook the viewer in the very first segment.
- Style guide for "{style}":
  informative   → clear, factual, confident narrator
  listicle      → numbered points, punchy, energetic
  storytelling  → narrative arc, emotional, descriptive
  educational   → step-by-step, patient, example-driven
"""


def generate_script(topic: str, duration: int = 60, style: str = "informative") -> dict:
    """
    Call GPT-4o to produce a structured video script.

    Returns a dict with keys: title, description, tags, segments.
    Each segment has: text, keywords, duration.
    """
    word_count = int(duration * 2.5)  # ~2.5 words per second of speech

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": SCRIPT_PROMPT.format(
                    topic=topic,
                    duration=duration,
                    word_count=word_count,
                    style=style,
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    raw = response.choices[0].message.content
    script = json.loads(raw)

    # Basic validation
    assert "segments" in script and len(script["segments"]) > 0, (
        "GPT returned no segments"
    )

    return script
