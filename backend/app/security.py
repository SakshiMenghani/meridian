import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus

from cryptography.fernet import Fernet, InvalidToken


def encrypt_secret(value: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(value.encode()).decode()


def decrypt_secret(token: str, key: str) -> str:
    try:
        return Fernet(key.encode()).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored secret could not be decrypted. Check APP_SECRET_KEY.") from exc


def scrub_text(message: str, secrets: list[str | None]) -> str:
    cleaned = message
    for secret in secrets:
        if not secret or len(secret) < 3:
            continue
        cleaned = cleaned.replace(secret, "********")
        cleaned = cleaned.replace(quote_plus(secret), "********")
    return cleaned[:800]


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)
