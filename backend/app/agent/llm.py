import json
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def llm_available() -> bool:
    return bool(get_settings().openai_api_key.strip())


def model_name() -> str:
    return get_settings().openai_model


def chat_json(system: str, payload: dict, *, temperature: float = 0) -> dict | None:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key.strip(), timeout=45)
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
        )
        text = response.choices[0].message.content or ""
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        logger.warning("LLM call failed: %s", str(exc).splitlines()[0][:200])
        return None
