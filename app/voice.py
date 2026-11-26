import os
import requests
import subprocess

from pathlib import Path

from app.config import (
    TEMP_DIR,
    TTS_API_URL,
    TTS_API_KEY
)


def generate_voice(
    text,
    project_id,
    voice_name="Burmese Narrator"
):
    if not TTS_API_URL:
        raise RuntimeError(
            "TTS_API_URL is not configured. "
            "Connect a Burmese-compatible speech provider."
        )

    output_dir = TEMP_DIR / project_id / "voice"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "narration.wav"

    headers = {}

    if TTS_API_KEY:
        headers["Authorization"] = (
            f"Bearer {TTS_API_KEY}"
        )

    payload = {
        "text": text,
        "voice": voice_name,
        "language": "my-MM",
        "style": (
            "Professional Burmese male narrator, "
            "warm deep voice, clear pronunciation, "
            "controlled suspense, natural pacing."
        )
    }

    response = requests.post(
        TTS_API_URL,
        json=payload,
        headers=headers,
        timeout=300
    )

    response.raise_for_status()

    output_path.write_bytes(response.content)

    if not output_path.exists() or output_path.stat().st_size < 100:
        raise RuntimeError("Voice file generation failed.")

    return str(output_path)


def get_audio_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(result.stdout.strip())
