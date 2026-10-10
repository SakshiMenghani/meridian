from dataclasses import dataclass


@dataclass
class ResolvedSource:
    id: str
    name: str
    source_type: str
    config: dict
    secret: str | None
