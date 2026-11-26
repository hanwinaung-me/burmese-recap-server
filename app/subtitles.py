import re
from pathlib import Path

from app.config import TEMP_DIR


def split_burmese_sentences(text):
    text = text.replace("\r", "\n")

    parts = re.split(
        r"(?<=[။!?])\s*|\n+",
        text
    )

    return [
        item.strip()
        for item in parts
        if item.strip()
    ]


def create_srt(sentences, duration, output_path):
    if not sentences:
        raise ValueError("No subtitle sentences.")

    total_chars = sum(
        max(len(sentence), 1)
        for sentence in sentences
    )

    current = 0.0
    output = []

    for index, sentence in enumerate(sentences):
        allocated = (
            duration
            * max(len(sentence), 1)
            / total_chars
        )

        start = current
        end = min(duration, current + allocated)

        output.append(
            f"{index + 1}\n"
            f"{timestamp(start)} --> {timestamp(end)}\n"
            f"{sentence}\n"
        )

        current = end

    Path(output_path).write_text(
        "\n".join(output),
        encoding="utf-8"
    )

    return str(output_path)


def timestamp(seconds):
    milliseconds = int(seconds * 1000)

    hours = milliseconds // 3600000
    minutes = (milliseconds % 3600000) // 60000
    secs = (milliseconds % 60000) // 1000
    millis = milliseconds % 1000

    return (
        f"{hours:02}:"
        f"{minutes:02}:"
        f"{secs:02},"
        f"{millis:03}"
    )


def generate_subtitles(text, duration, project_id):
    output_dir = TEMP_DIR / project_id / "subtitles"
    output_dir.mkdir(parents=True, exist_ok=True)

    sentences = split_burmese_sentences(text)

    output_path = output_dir / "subtitles.srt"

    return create_srt(
        sentences,
        duration,
        output_path
  )
