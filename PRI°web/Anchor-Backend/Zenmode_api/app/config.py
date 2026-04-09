import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = os.environ.get("APP_NAME", "ANCHOR").strip() or "ANCHOR"
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)
DEMO_MODE = os.environ.get("DEMO_MODE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
DB_FILE = Path(
    os.environ.get("DB_FILE", str(BASE_DIR / "users.db"))
).resolve()

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
GOAL_TITLE_MAX_LENGTH = 100
GOAL_DESCRIPTION_MAX_LENGTH = 300
STEP_TITLE_MAX_LENGTH = 100
CHECKIN_NOTE_MAX_LENGTH = 240

ALLOWED_GOAL_CATEGORIES = {
    "study",
    "sleep",
    "exercise",
    "reading",
    "focus",
    "general",
}
ALLOWED_GOAL_STATUSES = {"active", "paused", "completed"}

FRONTEND_FILE = Path(
    os.environ.get("FRONTEND_FILE", str(BASE_DIR.parent.parent / "anchor-landing.html"))
).resolve()
APP_PREVIEW_FILE = Path(
    os.environ.get("APP_PREVIEW_FILE", str(BASE_DIR.parent.parent / "anchor-app.html"))
).resolve()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/models",
).strip()
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "25"))
