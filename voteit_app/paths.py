import os
import sys
from pathlib import Path


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "VoteIt"
        return Path.home() / "AppData" / "Local" / "VoteIt"
    return Path(__file__).resolve().parent.parent


BASE_DIR = app_base_dir()
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = DATA_DIR / "candidate_photos"
DB_PATH = DATA_DIR / "voteit.sqlite3"
EXPORT_DIR = BASE_DIR / "exports"


def ensure_app_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
