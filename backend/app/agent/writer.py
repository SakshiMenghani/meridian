import json
import re

from app.config import get_settings


def polish_answer(question: str, draft: str, rows: list[dict], columns: list[str]) -> tuple[str, str | None]:
    """Rewrite the draft in plain language. Numbers must come from the draft or rows."""
    settings = get_settings()
    if not settings.openai_api_key.strip():
        return draft, None
    facts = {
        "question": question,
        "draft": draft,
        "columns": columns,
        "rows": rows[:20],
    }
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key.strip())
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write short answers for a data assistant. "
                        "Use only numbers and names that appear in the JSON. "
                        "Do not invent metrics, dates, or campaigns. "
                        "Two to four sentences. Plain language. No markdown."
                    ),
                },
                {"role": "user", "content": json.dumps(facts, default=str)},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text or _invented_number(text, draft, rows):
            return draft, None
        return text, settings.openai_model
    except Exception:
        return draft, None


def _invented_number(text: str, draft: str, rows: list[dict]) -> bool:
    allowed = _numbers(draft)
    for row in rows:
        for value in row.values():
            allowed.update(_numbers(str(value)))
            allowed.update(_numbers(_commas(value)))
    used = _numbers(text)
    return bool(used - allowed)


def _commas(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _numbers(text: str) -> set[str]:
    found = set()
    for match in re.findall(r"\d[\d,]*\.?\d*", text):
        found.add(match.replace(",", ""))
    return found
