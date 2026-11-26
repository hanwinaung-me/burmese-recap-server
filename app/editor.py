import subprocess
from pathlib import Path

from app.config import (
    OUTPUT_DIR,
    TEMP_DIR,
    FFMPEG_TIMEOUT
)


def run_ffmpeg(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=FFMPEG_TIMEOUT
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:])

    return True


def escape_subtitle_path(path):
    return (
        str(Path(path).resolve())
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def render_video(
    project_id,
    source_video,
    narration_audio,
    subtitle_file,
    aspect_ratio="16:9",
    resolution="1080p",
    music_file=None
):
    output_path = OUTPUT_DIR / f"{project_id}_final.mp4"

    ratios = {
        "16:9": "1920:1080",
        "9:16": "1080:1920",
        "1:1": "1080:1080"
    }

    sizes = {
        "720p": {
            "16:9": "1280:720",
            "9:16": "720:1280",
            "1:1": "720:720"
        },
        "1080p": {
            "16:9": "1920:1080",
            "9:16": "1080:1920",
            "1:1": "1080:1080"
        }
    }

    if aspect_ratio not in ratios:
        raise ValueError("Invalid aspect ratio.")

    if resolution not in sizes:
        raise ValueError("Invalid resolution.")

    target_size = sizes[resolution][aspect_ratio]

    width, height = target_size.split(":")

    subtitle_filter = ""

    if subtitle_file:
        subtitle_path = escape_subtitle_path(
            subtitle_file
        )

        subtitle_filter = (
            f",subtitles='{subtitle_path}'"
            ":force_style='FontName=Noto Sans Myanmar,"
            "FontSize=24,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Outline=2,"
            "Shadow=1,Alignment=2,MarginV=40'"
        )

    scale_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        f"{subtitle_filter}"
    )

    if music_file:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i", str(source_video),
            "-i", str(narration_audio),
            "-stream_loop", "-1",
            "-i", str(music_file),
            "-filter_complex",
            (
                "[1:a]volume=1.0[voice];"
                "[2:a]volume=0.12[music];"
                "[voice][music]"
                "amix=inputs=2:duration=first:dropout_transition=2[a]"
            ),
            "-map", "0:v:0",
            "-map", "[a]",
            "-vf", scale_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]
    else:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i", str(source_video),
            "-i", str(narration_audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", scale_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]

    run_ffmpeg(command)

    return str(output_path)
