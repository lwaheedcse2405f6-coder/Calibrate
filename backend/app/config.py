from pathlib import Path

from dotenv import load_dotenv
import os

# .env lives at the project root, two folders above this file's folder
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL_REASON = os.getenv("GROQ_MODEL_REASON", "openai/gpt-oss-120b")
GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "")
