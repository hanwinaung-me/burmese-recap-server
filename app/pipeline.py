import json
import threading
import traceback

from app import database
from app.jobs import set_stage, fail_job, now
from app.video import split_video
from app.scene_analysis import (
    extract_frames,
    analyze_frames
)
from app.ai import (
    analyze_segment,
    create_story_outline,
    create_recap_script
)
from app.config import TEMP_DIR


def run_analysis(project_id):
    try:
        project = database.get_project(project_id)

        if not project or not project.get("video_path"):
            raise RuntimeError("Project has no uploaded video.")

        video_path = project["video_path"]

        set_stage(
            project_id,
            "SPLITTING",
            10,
            "Preparing video segments."
        )

        segments = split_video(video_path, project_id)

        analyses = []

        for index, segment in enumerate(segments):
            progress = 15 + int(
                55 * (index / max(len(segments), 1))
            )

            set_stage(
                project_id,
                "ANALYZING",
                progress,
                f"Analyzing segment {index + 1}/{len(segments)}."
            )

            frames = extract_frames(
                str(segment),
                f"{project_id}_{index}"
            )

            visual_notes = analyze_frames(frames)

            analysis = analyze_segment(
                index + 1,
                len(segments),
                visual_notes
            )

            analyses.append(analysis)

            output_dir = TEMP_DIR / project_id
            output_dir.mkdir(parents=True, exist_ok=True)

            (output_dir / f"analysis_{index + 1}.json").write_text(
                analysis,
                encoding="utf-8"
            )

        set_stage(
            project_id,
            "STORY_OUTLINE",
            75,
            "Building the complete story outline."
        )

        outline = create_story_outline(analyses)

        set_stage(
            project_id,
            "SCRIPT_GENERATING",
            90,
            "Writing Burmese recap narration."
        )

        script = create_recap_script(outline)

        output_dir = TEMP_DIR / project_id
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "story_outline.txt").write_text(
            outline,
            encoding="utf-8"
        )

        (output_dir / "script.txt").write_text(
            script,
            encoding="utf-8"
        )

        database.update_project(
            project_id,
            status="SCRIPT_READY",
            progress=100,
            message="Burmese recap script generated.",
            settings={
                "outline": outline,
                "script": script
            }
        )

        database.add_event(
            project_id,
            "SCRIPT_READY",
            "Script generation completed.",
            now()
        )

    except Exception as error:
        fail_job(
            project_id,
            traceback.format_exc()
        )


def start_analysis(project_id):
    thread = threading.Thread(
        target=run_analysis,
        args=(project_id,),
        daemon=True
    )

    thread.start()
