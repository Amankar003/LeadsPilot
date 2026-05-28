from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailDraftPayload:
    subject: str
    opening_line: str
    body: str
    cta: str
    personalization_reason: str
    confidence_score: float = 0.5
    followups: list[dict[str, Any]] = field(default_factory=list)
