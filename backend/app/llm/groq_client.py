"""Groq client: JSON-only answers, retries with a growing wait, disk cache."""

import hashlib
import json
import time
from pathlib import Path

import groq

from app import config

# backend/.cache/llm (Git ignores backend/.cache/)
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm"

_client = None


class LLMError(Exception):
    """A friendly error message the API can show to users."""


def _get_client():
    """Create the Groq client the first time it is needed, not at import."""
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise LLMError("The AI key is not set. Add GROQ_API_KEY to your .env file.")
        _client = groq.Groq(api_key=config.GROQ_API_KEY)
    return _client


def ask_json(system: str, user: str, model: str | None = None, retries: int = 2) -> dict:
    """Ask Groq a question and return the answer as a Python dict."""
    model = model or config.GROQ_MODEL_FAST
    key = hashlib.sha256(f"{model}|{system}|{user}".encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"

    # 1. Same question asked before? Return the saved answer for free.
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    last_problem = "unknown problem"
    for attempt in range(retries + 1):
        try:
            response = _get_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system + " Reply with JSON only."},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            data = json.loads(response.choices[0].message.content)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        except groq.AuthenticationError:
            raise LLMError("The AI key was rejected. Check GROQ_API_KEY in your .env file.")
        except groq.RateLimitError:
            last_problem = "rate limit"
            time.sleep(5 * (attempt + 1))  # too many requests: wait longer each time
        except (groq.APIError, json.JSONDecodeError, TypeError):
            last_problem = "bad or failed reply"
            time.sleep(2 * (attempt + 1))

    if last_problem == "rate limit":
        raise LLMError("The AI is busy right now (rate limit). Please try again in a minute.")
    raise LLMError("The AI could not give a valid answer. Please try again.")