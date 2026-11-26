
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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import database
from app.config import (
    APP_NAME,
    MAX_UPLOAD_MB,
    UPLOAD_DIR,
    OUTPUT_DIR
)
from app.video import (
    check_tools,
    probe_video
)
from app.jobs import now
from app.pipeline import start_analysis
from app.voice import (
    generate_voice,
    get_audio_duration
)
from app.subtitles import generate_subtitles
from app.editor import render_video


# ==========================================
# APPLICATION
# ==========================================

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

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v"
}


# ==========================================
# FRONTEND
# ==========================================

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)


@app.get("/")
def home():
    return {
        "app": APP_NAME,
        "status": "ok",
        "version": "1.0.0",
        "studio": "/studio"
    }


@app.get("/studio")
def studio():
    index_file = STATIC_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            404,
            "Frontend index.html not found."
        )

    return FileResponse(index_file)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health():
    tools = check_tools()

    return {
        "status": "ok",
        "app": APP_NAME,
        "ffmpeg": tools["ffmpeg"],
        "ffprobe": tools["ffprobe"]
    }


# ==========================================
# PROJECT MANAGEMENT
# ==========================================

@app.get("/api/projects")
def projects():
    return {
        "projects": database.list_projects()
    }


@app.post("/api/projects")
def create_project(
    name: str = Form("New Recap Project")
):
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


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    return {
        "project": project,
        "events": database.get_events(project_id)
    }


# ==========================================
# VIDEO UPLOAD
# ==========================================

@app.post("/api/projects/{project_id}/upload")
async def upload_video(
    project_id: str,
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(False)
):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    if not rights_confirmed:
        raise HTTPException(
            400,
            "Please confirm you have permission to process this video."
        )

    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

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

    finally:
        await file.close()

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
        original_filename=filename,
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


@app.get("/api/projects/{project_id}/video-info")
def video_info(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    video_path = project.get("video_path")

    if not video_path or not Path(video_path).exists():
        raise HTTPException(
            400,
            "No video uploaded."
        )

    return probe_video(video_path)


# ==========================================
# AI STORY ANALYSIS
# ==========================================

@app.post("/api/projects/{project_id}/analyze")
def analyze_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    video_path = project.get("video_path")

    if not video_path or not Path(video_path).exists():
        raise HTTPException(
            400,
            "Upload a video first."
        )

    if project.get("status") in [
        "QUEUED",
        "SPLITTING",
        "ANALYZING",
        "SCRIPT_GENERATING"
    ]:
        raise HTTPException(
            409,
            "Project is already processing."
        )

    database.update_project(
        project_id,
        status="QUEUED",
        progress=1,
        message="Analysis queued."
    )

    try:
        start_analysis(project_id)

    except Exception as error:
        database.update_project(
            project_id,
            status="FAILED",
            message=str(error)
        )

        raise HTTPException(
            500,
            f"Could not start analysis: {error}"
        )

    return {
        "success": True,
        "message": "Analysis started."
    }


# ==========================================
# SCRIPT EDITOR
# ==========================================

@app.get("/api/projects/{project_id}/script")
def get_script(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    settings = project.get("settings") or {}

    return {
        "script": settings.get("script", ""),
        "outline": settings.get("outline", "")
    }


@app.put("/api/projects/{project_id}/script")
def edit_script(
    project_id: str,
    script: str = Form(...)
):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    if not script.strip():
        raise HTTPException(
            400,
            "Script cannot be empty."
        )

    settings = project.get("settings") or {}
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


# ==========================================
# BURMESE VOICE GENERATION
# ==========================================

@app.post("/api/projects/{project_id}/voice")
def create_voice(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    settings = project.get("settings") or {}
    script = settings.get("script", "")

    if not script.strip():
        raise HTTPException(
            400,
            "Generate or save a script first."
        )

    try:
        voice_path = generate_voice(
            script,
            project_id
        )

        duration = get_audio_duration(voice_path)

        settings["voice_path"] = str(voice_path)
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

    except Exception as error:
        raise HTTPException(
            500,
            f"Voice generation failed: {error}"
        )


# ==========================================
# SUBTITLE GENERATION
# ==========================================

@app.post("/api/projects/{project_id}/subtitles")
def create_subtitles(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    settings = project.get("settings") or {}

    script = settings.get("script", "")
    duration = settings.get("voice_duration")

    if not script or not duration:
        raise HTTPException(
            400,
            "Generate script and voice first."
        )

    try:
        subtitle_path = generate_subtitles(
            script,
            duration,
            project_id
        )

        settings["subtitle_path"] = str(subtitle_path)

        database.update_project(
            project_id,
            settings=settings,
            status="SUBTITLES_READY",
            message="Subtitles generated."
        )

        return {
            "success": True,
            "subtitle_path": str(subtitle_path)
        }

    except Exception as error:
        raise HTTPException(
            500,
            f"Subtitle generation failed: {error}"
        )


# ==========================================
# VIDEO EXPORT / EDITING
# ==========================================

@app.post("/api/projects/{project_id}/render")
def export_project(
    project_id: str,
    aspect_ratio: str = Form("16:9"),
    resolution: str = Form("1080p")
):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    settings = project.get("settings") or {}

    video_path = project.get("video_path")
    voice_path = settings.get("voice_path")
    subtitle_path = settings.get("subtitle_path")

    if not video_path or not Path(video_path).exists():
        raise HTTPException(
            400,
            "Missing source video."
        )

    if not voice_path or not Path(voice_path).exists():
        raise HTTPException(
            400,
            "Generate voice first."
        )

    if not subtitle_path or not Path(subtitle_path).exists():
        raise HTTPException(
            400,
            "Generate subtitles first."
        )

    if aspect_ratio not in ["16:9", "9:16", "1:1"]:
        raise HTTPException(
            400,
            "Unsupported aspect ratio."
        )

    if resolution not in ["720p", "1080p"]:
        raise HTTPException(
            400,
            "Unsupported resolution."
        )

    database.update_project(
        project_id,
        status="RENDERING",
        progress=90,
        message="Rendering video."
    )

    try:
        output = render_video(
            project_id=project_id,
            source_video=video_path,
            narration_audio=voice_path,
            subtitle_file=subtitle_path,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        output = Path(output)

        if not output.exists():
            raise RuntimeError(
                "Render finished but output file was not found."
            )

        database.update_project(
            project_id,
            status="COMPLETED",
            progress=100,
            message="Export completed."
        )

        return {
            "success": True,
            "filename": output.name
        }

    except Exception as error:
        database.update_project(
            project_id,
            status="FAILED",
            message=f"Render failed: {error}"
        )

        raise HTTPException(
            500,
            f"Video rendering failed: {error}"
        )


# ==========================================
# DOWNLOAD FINAL VIDEO
# ==========================================

@app.get("/api/projects/{project_id}/download")
def download_project(project_id: str):
    project = database.get_project(project_id)

    if not project:
        raise HTTPException(
            404,
            "Project not found."
        )

    output = OUTPUT_DIR / f"{project_id}_final.mp4"

    if not output.exists():
        raise HTTPException(
            404,
            "Export not found."
        )

    return FileResponse(
        path=str(output),
        media_type="video/mp4",
        filename=output.name
    )
