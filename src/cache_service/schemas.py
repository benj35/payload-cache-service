"""Request/response schemas shared by the API and the CLI."""

from pydantic import BaseModel, Field, model_validator

# Bounds request size so a single call cannot make the service issue an
# unbounded number of transformer calls.
MAX_ITEMS = 10_000


class PayloadRequest(BaseModel):
    list_1: list[str] = Field(min_length=1, max_length=MAX_ITEMS)
    list_2: list[str] = Field(min_length=1, max_length=MAX_ITEMS)

    @model_validator(mode="after")
    def _lists_have_same_length(self) -> "PayloadRequest":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: str
    message: str


class PayloadRead(BaseModel):
    output: str
