from datetime import datetime, timezone

from app import database


def now():
    return datetime.now(timezone.utc).isoformat()


def set_stage(project_id, stage, progress, message):
    project = database.update_project(
        project_id,
        status=stage,
        progress=progress,
        message=message,
        error=""
    )

    database.add_event(
        project_id,
        stage,
        message,
        now()
    )

    return project


def fail_job(project_id, error):
    database.update_project(
        project_id,
        status="FAILED",
        message="Processing failed.",
        error=str(error)
    )

    database.add_event(
        project_id,
        "FAILED",
        str(error),
        now()
    )
