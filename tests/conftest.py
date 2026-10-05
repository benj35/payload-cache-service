import pytest
from fastapi.testclient import TestClient

from cache_service.config import ServerSettings
from cache_service.main import create_app


class RecordingTransformer:
    """Upper-cases like the real transformer but records every call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text: str) -> str:
        self.calls.append(text)
        return text.upper()


@pytest.fixture
def transformer() -> RecordingTransformer:
    return RecordingTransformer()


@pytest.fixture
def client(transformer: RecordingTransformer):
    app = create_app(ServerSettings(database_url="sqlite://"), transformer)
    with TestClient(app) as test_client:  # the context manager runs the lifespan
        yield test_client
