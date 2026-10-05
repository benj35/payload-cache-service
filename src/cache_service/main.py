"""FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from sqlmodel import Session

from . import service
from .config import ServerSettings
from .db import create_tables, get_session, make_engine
from .schemas import PayloadCreated, PayloadRead, PayloadRequest
from .transformer import Transformer, make_uppercase_transformer

SessionDep = Annotated[Session, Depends(get_session)]


def get_transformer(request: Request) -> Transformer:
    return request.app.state.transformer


TransformerDep = Annotated[Transformer, Depends(get_transformer)]


def create_app(
    settings: ServerSettings | None = None, transformer: Transformer | None = None
) -> FastAPI:
    """Application factory; ``transformer`` can be injected to observe calls in tests."""
    settings = settings or ServerSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = make_engine(settings.database_url)
        app.state.transformer = transformer or make_uppercase_transformer(
            settings.transform_latency_seconds
        )
        create_tables(app.state.engine)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Payload caching service", lifespan=lifespan)

    # Plain ``def`` endpoints: the DB driver and transformer are blocking, so
    # FastAPI runs them in a thread pool instead of stalling the event loop.
    @app.post("/payload", response_model=PayloadCreated, status_code=status.HTTP_201_CREATED)
    def create_payload(
        body: PayloadRequest,
        response: Response,
        session: SessionDep,
        transformer: TransformerDep,
    ) -> PayloadCreated:
        payload_id, created = service.create_payload(session, body, transformer)
        if not created:
            # Idempotent: the same input always yields the same, already stored, payload.
            response.status_code = status.HTTP_200_OK
        message = "Payload created" if created else "Payload already exists"
        return PayloadCreated(id=payload_id, message=message)

    @app.get("/payload/{payload_id}", response_model=PayloadRead)
    def read_payload(payload_id: str, session: SessionDep) -> PayloadRead:
        output = service.read_payload(session, payload_id)
        if output is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
        return PayloadRead(output=output)

    return app

