import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from app import database
from app.config import (
    APP_NAME,
    MAX_UPLOAD_MB,
    UPLOAD_DIR
)
from app.video import (
    check_tools,
    probe_video
)
from app.jobs import now

app = FastAPI(
    title=APP_NAME,
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

database.initialize()

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v"
}


@app.get("/")
def home():
    return {
        "app": APP_NAME,
        "status": "ok",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    tools = check_tools()

    return {
        "status": "ok",
        "app": APP_NAME,
        "ffmpeg": tools["ffmpeg"],
        "ffprobe": tools["ffprobe"]
    }


@app.get("/api/projects")
def projects():
    return {
        "projects": database.list_projects()
    }


@app.post("/api/projects")
def create_project(name: str = Form("New Recap Project")):
    project_id = str(uuid.uuid4())

    project = {
        "id": project_id,
        "name": name,
        "status": "CREATED",
        "progress": 0,
        "message": "Project created.",
        "created_at": now(),
        "updated_at": now()
    }

    database.create_project(project)

    return {
        "success": True,
        "project": database.get_project(project_id)
    }


@app.post("/api/projects/{project_id}/upload")
async def upload_video(
    project_id: str,
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(False)
):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    if not rights_confirmed:
        raise HTTPException(
            400,
            "Please confirm you have permission to process this video."
        )

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            "Unsupported video format."
        )

    destination = UPLOAD_DIR / (
        project_id + extension
    )

    total_size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(
                        413,
                        "Upload exceeds configured size limit."
                    )

                output.write(chunk)

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    try:
        info = probe_video(destination)
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            400,
            f"Invalid video or FFprobe error: {error}"
        )

    updated = database.update_project(
        project_id,
        original_filename=file.filename,
        video_path=str(destination),
        video_size=total_size,
        duration=info["duration"],
        status="UPLOADED",
        progress=5,
        message="Video uploaded and checked."
    )

    return {
        "success": True,
        "project": updated,
        "video_info": info
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    return {
        "project": project,
        "events": database.get_events(project_id)
    }


@app.get("/api/projects/{project_id}/video-info")
def video_info(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    if not project.get("video_path"):
        raise HTTPException(400, "No video uploaded.")

    return probe_video(project["video_path"])
from app.pipeline import start_analysis
from app.ai import create_recap_script
from app.voice import generate_voice, get_audio_duration
from app.subtitles import generate_subtitles
from app.editor import render_video
from app.config import OUTPUT_DIR, TEMP_DIR


@app.post("/api/projects/{project_id}/analyze")
def analyze_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    if not project.get("video_path"):
        raise HTTPException(400, "Upload a video first.")

    if project["status"] in [
        "ANALYZING",
        "SPLITTING",
        "SCRIPT_GENERATING"
    ]:
        raise HTTPException(409, "Project is already processing.")

    start_analysis(project_id)

    database.update_project(
        project_id,
        status="QUEUED",
        progress=1,
        message="Analysis queued."
    )

    return {
        "success": True,
        "message": "Analysis started."
    }


@app.get("/api/projects/{project_id}/script")
def get_script(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    return {
        "script": project.get("settings", {}).get("script", ""),
        "outline": project.get("settings", {}).get("outline", "")
    }


@app.put("/api/projects/{project_id}/script")
def edit_script(project_id: str, script: str = Form(...)):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    settings = project.get("settings", {})
    settings["script"] = script

    database.update_project(
        project_id,
        settings=settings,
        status="SCRIPT_APPROVED",
        message="Script saved."
    )

    return {
        "success": True,
        "script": script
    }


@app.post("/api/projects/{project_id}/voice")
def create_voice(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    script = project.get("settings", {}).get("script", "")

    if not script:
        raise HTTPException(400, "Generate or save a script first.")

    voice_path = generate_voice(
        script,
        project_id
    )

    duration = get_audio_duration(voice_path)

    settings = project.get("settings", {})
    settings["voice_path"] = voice_path
    settings["voice_duration"] = duration

    database.update_project(
        project_id,
        settings=settings,
        status="VOICE_READY",
        message="Voice generated."
    )

    return {
        "success": True,
        "duration": duration
    }


@app.post("/api/projects/{project_id}/subtitles")
def create_subtitles(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    settings = project.get("settings", {})
    script = settings.get("script", "")
    duration = settings.get("voice_duration")

    if not script or not duration:
        raise HTTPException(
            400,
            "Generate script and voice first."
        )

    subtitle_path = generate_subtitles(
        script,
        duration,
        project_id
    )

    settings["subtitle_path"] = subtitle_path

    database.update_project(
        project_id,
        settings=settings,
        status="SUBTITLES_READY",
        message="Subtitles generated."
    )

    return {
        "success": True,
        "subtitle_path": subtitle_path
    }


@app.post("/api/projects/{project_id}/render")
def export_project(
    project_id: str,
    aspect_ratio: str = Form("16:9"),
    resolution: str = Form("1080p")
):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    settings = project.get("settings", {})

    if not project.get("video_path"):
        raise HTTPException(400, "Missing source video.")

    if not settings.get("voice_path"):
        raise HTTPException(400, "Generate voice first.")

    if not settings.get("subtitle_path"):
        raise HTTPException(400, "Generate subtitles first.")

    output = render_video(
        project_id=project_id,
        source_video=project["video_path"],
        narration_audio=settings["voice_path"],
        subtitle_file=settings["subtitle_path"],
        aspect_ratio=aspect_ratio,
        resolution=resolution
    )

    database.update_project(
        project_id,
        status="COMPLETED",
        progress=100,
        message="Export completed."
    )

    return {
        "success": True,
        "filename": Path(output).name
    }


@app.get("/api/projects/{project_id}/download")
def download_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(404, "Project not found.")

    output = OUTPUT_DIR / f"{project_id}_final.mp4"

    if not output.exists():
        raise HTTPException(404, "Export not found.")

    return FileResponse(
        output,
        media_type="video/mp4",
        filename=output.name
    )
