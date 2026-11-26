import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv(
    "APP_NAME",
    "Burmese Recap Studio"
)

APP_ENV = os.getenv("APP_ENV", "development")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
CHUNK_MINUTES = int(os.getenv("CHUNK_MINUTES", "8"))
FRAME_INTERVAL_SECONDS = int(
    os.getenv("FRAME_INTERVAL_SECONDS", "15")
)

FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "7200"))

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/burmese_recap"))
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    str(DATA_DIR / "recap.db")
)

UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"

for directory in [
    DATA_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    TEMP_DIR
]:
    directory.mkdir(parents=True, exist_ok=True)
