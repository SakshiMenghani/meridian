import re

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str) -> str:
    if not isinstance(name, str) or len(name) > 80 or not IDENT.fullmatch(name):
        raise ValueError("Invalid identifier.")
    return f'"{name}"'


def sanitize_ident(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{cleaned}".strip("_") if cleaned else "column"
    return cleaned[:60]
