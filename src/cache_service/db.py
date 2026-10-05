"""Engine and session plumbing."""

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


def make_engine(database_url: str) -> Engine:
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        # FastAPI runs sync endpoints in a thread pool, so connections hop threads.
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            # An in-memory database exists per connection; share a single one.
            kwargs["poolclass"] = StaticPool
        else:
            path = database_url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, **kwargs)


def create_tables(engine: Engine) -> None:
    # Shortcut: no migrations tool for two tables; add Alembic once the schema evolves.
    SQLModel.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
