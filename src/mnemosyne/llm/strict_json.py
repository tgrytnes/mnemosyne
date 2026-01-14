import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class StrictJsonError(RuntimeError):
    """Raised when strict JSON enforcement fails."""


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_step(value: str) -> str:
    return value.strip().lower().replace("-", "_")


@dataclass(frozen=True)
class StrictJsonConfig:
    steps: frozenset[str]
    allow_fallback: bool

    @classmethod
    def from_env(cls) -> "StrictJsonConfig":
        raw_steps = os.getenv("STRICT_JSON_STEPS", "").strip()
        allow_fallback = _parse_bool(os.getenv("ALLOW_JSON_FALLBACK", "false"))

        if not raw_steps:
            return cls(steps=frozenset(), allow_fallback=allow_fallback)

        tokens = []
        for part in raw_steps.split(","):
            tokens.extend(part.split())
        normalized = {_normalize_step(token) for token in tokens if token.strip()}

        if "all" in normalized or "*" in normalized:
            return cls(steps=frozenset({"*"}), allow_fallback=allow_fallback)

        return cls(steps=frozenset(normalized), allow_fallback=allow_fallback)

    def is_strict(self, step: str) -> bool:
        if "*" in self.steps:
            return True
        return _normalize_step(step) in self.steps
