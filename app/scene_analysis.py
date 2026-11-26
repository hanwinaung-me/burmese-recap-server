import base64
import json
import requests

from pathlib import Path

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    FRAME_INTERVAL_SECONDS,
    TEMP_DIR
)

from app.video import run_command


def extract_frames(video_path, project_id):
    output_dir = TEMP_DIR / project_id / "frames"
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(output_dir / "frame_%06d.jpg")

    run_command([
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i", str(video_path),
        "-vf",
        f"fps=1/{FRAME_INTERVAL_SECONDS},scale=768:-2",
        "-q:v", "4",
        pattern
    ])

    return sorted(output_dir.glob("frame_*.jpg"))


def image_to_base64(path):
    return base64.b64encode(
        Path(path).read_bytes()
    ).decode("utf-8")


def analyze_frames(frames):
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing Gemini API Key.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_API_KEY
    )

    parts = [{
        "text": """
Analyze these movie frames in chronological order.

Write concise, factual Burmese visual observations.

Identify:
- Visible characters
- Actions
- Locations
- Objects
- Important changes between frames

Do not invent dialogue, unseen actions or story details.
Return JSON array with one observation per frame.
"""
    }]

    for frame in frames[:40]:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_to_base64(frame)
            }
        })

    response = requests.post(
        url,
        json={
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192
            }
        },
        timeout=240
    )

    response.raise_for_status()

    data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]
