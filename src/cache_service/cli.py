"""``cache-cli``: exercise a running caching service from the command line.

Flags are parsed and validated by Pydantic Settings. The spec uses ``-h`` for
both ``--host`` and ``--help``, which cannot work; ``-h`` stays the conventional
help flag and the host short flag is ``-H``.
"""

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, TextIO

import httpx
from pydantic import AliasChoices, AnyHttpUrl, Field, PositiveInt, ValidationError, model_validator
from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict

from .schemas import PayloadCreated, PayloadRead, PayloadRequest

STDIO = "-"


class CliSettings(BaseSettings):
    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        cli_exit_on_error=False,
        cli_hide_none_type=True,
        case_sensitive=True,  # otherwise the "H" alias is lower-cased and clashes with -h
    )

    host: Annotated[
        AnyHttpUrl,
        Field(
            validation_alias=AliasChoices("H", "host"),
            description="Base URL of the caching service",
        ),
    ] = AnyHttpUrl("http://localhost:8000")
    repeat: Annotated[
        PositiveInt,
        Field(
            validation_alias=AliasChoices("r", "repeat"),
            description="Number of POST+GET iterations (repeats should hit the cache)",
        ),
    ] = 1
    input: Annotated[
        str | None,
        Field(
            validation_alias=AliasChoices("i", "input"),
            description=f"File with the JSON request body ('{STDIO}' for stdin)",
        ),
    ] = None
    json_body: Annotated[
        str | None,
        Field(
            validation_alias=AliasChoices("j", "json"),
            description="JSON request body given inline",
        ),
    ] = None
    output: Annotated[
        str,
        Field(
            validation_alias=AliasChoices("o", "output"),
            description=f"File to write results to ('{STDIO}' for stdout)",
        ),
    ] = STDIO

    @model_validator(mode="after")
    def _exactly_one_input_source(self) -> "CliSettings":
        if (self.input is None) == (self.json_body is None):
            raise ValueError("provide exactly one of --input and --json")
        return self


def read_request(settings: CliSettings, stdin: TextIO) -> PayloadRequest:
    if settings.json_body is not None:
        raw = settings.json_body
    elif settings.input == STDIO:
        raw = stdin.read()
    else:
        raw = Path(settings.input).read_text(encoding="utf-8")  # type: ignore[arg-type]
    return PayloadRequest.model_validate_json(raw)


def run(settings: CliSettings, client: httpx.Client, stdin: TextIO, out: TextIO) -> None:
    """Create the payload and read it back, ``repeat`` times; one JSON line per iteration."""
    request = read_request(settings, stdin)
    for _ in range(settings.repeat):
        created = client.post("/payload", json=request.model_dump())
        created.raise_for_status()
        payload_id = PayloadCreated.model_validate(created.json()).id

        read = client.get(f"/payload/{payload_id}")
        read.raise_for_status()
        output = PayloadRead.model_validate(read.json()).output

        result = {
            "id": payload_id,
            "created": created.status_code == httpx.codes.CREATED,
            "output": output,
            "elapsed_ms": round((created.elapsed + read.elapsed).total_seconds() * 1000),
        }
        out.write(json.dumps(result) + "\n")


def parse_args(argv: list[str] | None = None) -> CliSettings:
    return CliApp.run(CliSettings, cli_args=sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    try:
        settings = parse_args(argv)
        with (
            httpx.Client(base_url=str(settings.host), timeout=30) as client,
            _open_output(settings.output) as out,
        ):
            run(settings, client, sys.stdin, out)
    except (ValidationError, OSError, httpx.HTTPError) as error:
        print(f"cache-cli: error: {error}", file=sys.stderr)
        return 1
    return 0


@contextmanager
def _open_output(target: str) -> Iterator[TextIO]:
    """Yield stdout for ``-`` (left open) or the named file (closed afterwards)."""
    if target == STDIO:
        yield sys.stdout
    else:
        with open(target, "w", encoding="utf-8") as file:
            yield file


if __name__ == "__main__":
    raise SystemExit(main())
