import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(BASE_DIR.parent / "frontend")))


def _path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default)))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    DATABASE = str(_path("DATABASE_PATH", BASE_DIR / "database" / "app.db"))
    KB_DIR = _path("KB_DIR", BASE_DIR / "knowledge_base")
    MODEL_DIR = _path("MODEL_DIR", BASE_DIR / "models" / "qwen")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    INGEST_SYNC = False  # tests process uploads inline

    QWEN_REPO = os.getenv("QWEN_REPO", "Qwen/Qwen2.5-1.5B-Instruct-GGUF")
    QWEN_FILE = os.getenv("QWEN_FILE", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
    LLM_CONTEXT = int(os.getenv("LLM_CONTEXT", "4096"))
    LLM_THREADS = int(os.getenv("LLM_THREADS", "0"))

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "400"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    TOP_K = int(os.getenv("TOP_K", "4"))
    MIN_SCORE = float(os.getenv("MIN_SCORE", "0.25"))
