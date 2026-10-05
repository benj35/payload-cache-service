"""Payload generation with transformer-result caching.

Two caching layers keep calls to the (expensive) transformer minimal:

1. Payloads are addressed by a digest of their input, so a repeated request is
   answered from the database without any transformation.
2. Transformed strings are cached individually, so a *new* payload only pays
   for strings never seen before in any earlier payload, and for each distinct
   string only once even if it occurs several times in the request.
"""

import hashlib
import json
from collections.abc import Iterable, Iterator, Sequence
from itertools import chain
from typing import Any

from sqlalchemy import insert as generic_insert
from sqlmodel import Session, col, select

from .models import Payload, TransformedString
from .schemas import PayloadRequest
from .transformer import Transformer

# Stays below SQLite's historic limit of 999 bound parameters per statement.
_CHUNK_SIZE = 500


def compute_payload_id(request: PayloadRequest) -> str:
    # JSON (not plain concatenation) so that ["a, b"] and ["a", "b"] cannot collide.
    canonical = json.dumps(
        [request.list_1, request.list_2], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return list(chain.from_iterable(zip(first, second, strict=True)))


def create_payload(
    session: Session, request: PayloadRequest, transformer: Transformer
) -> tuple[str, bool]:
    """Generate and store the payload; return ``(payload_id, newly_created)``."""
    payload_id = compute_payload_id(request)
    if session.get(Payload, payload_id) is not None:
        return payload_id, False

    transformed = _transform_all(session, request.list_1 + request.list_2, transformer)
    output = ", ".join(
        transformed[text] for text in interleave(request.list_1, request.list_2)
    )

    inserted = _insert_ignore(session, Payload, [{"id": payload_id, "output": output}])
    session.commit()
    # If a concurrent request stored the same payload first, nothing was inserted.
    return payload_id, inserted == 1


def read_payload(session: Session, payload_id: str) -> str | None:
    payload = session.get(Payload, payload_id)
    return payload.output if payload else None


def _transform_all(
    session: Session, texts: Iterable[str], transformer: Transformer
) -> dict[str, str]:
    """Return ``{text: transformed}``, calling the transformer only for cache misses."""
    unique = list(dict.fromkeys(texts))
    results = _load_cached(session, unique)

    fresh = {text: transformer(text) for text in unique if text not in results}
    if fresh:
        rows = [{"source": text, "result": result} for text, result in fresh.items()]
        _insert_ignore(session, TransformedString, rows)
        results.update(fresh)
    return results


def _load_cached(session: Session, texts: Sequence[str]) -> dict[str, str]:
    cached: dict[str, str] = {}
    for chunk in _chunks(texts, _CHUNK_SIZE):
        statement = select(TransformedString).where(
            col(TransformedString.source).in_(chunk)
        )
        cached.update((row.source, row.result) for row in session.exec(statement))
    return cached


def _insert_ignore(session: Session, model: type, rows: list[dict[str, Any]]) -> int:
    """Insert rows, silently skipping primary-key conflicts; return rows inserted.

    Concurrent requests may race to store the same (deterministic) row. Losing
    that race is harmless, so it must not surface as an error.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover
        insert = generic_insert
    inserted = 0
    for chunk in _chunks(rows, _CHUNK_SIZE):
        statement = insert(model)
        if hasattr(statement, "on_conflict_do_nothing"):
            statement = statement.on_conflict_do_nothing()
        inserted += session.connection().execute(statement, chunk).rowcount
    return inserted


def _chunks[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
