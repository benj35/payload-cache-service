"""The "transformer function" that stands in for an external service."""

import time
from collections.abc import Callable

Transformer = Callable[[str], str]


def make_uppercase_transformer(latency_seconds: float = 0.0) -> Transformer:
    """Build a transformer that upper-cases its input after an optional delay."""

    def transform(text: str) -> str:
        if latency_seconds:
            time.sleep(latency_seconds)
        return text.upper()

    return transform
