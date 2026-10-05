"""Database tables."""

from sqlmodel import Field, SQLModel


class TransformedString(SQLModel, table=True):
    """Cached outcome of one call to the transformer function.

    The transformer is a pure function of its input, so the source string is
    the natural primary key. Shortcut: on PostgreSQL very long strings would
    exceed the btree index row limit; keying by a hash would lift that.
    """

    source: str = Field(primary_key=True)
    result: str


class Payload(SQLModel, table=True):
    """A generated payload.

    ``id`` is a digest of the request, which makes identical requests map to
    the same identifier without any lookup table.
    """

    id: str = Field(primary_key=True)
    output: str
