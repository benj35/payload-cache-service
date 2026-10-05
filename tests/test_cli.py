import io
import json

import pytest
from pydantic import ValidationError

from cache_service.cli import CliSettings, parse_args, run

BODY = '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'


def run_cli(client, argv, stdin=""):
    out = io.StringIO()
    run(parse_args(argv), client, io.StringIO(stdin), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_inline_json_creates_and_reads_payload(client):
    [result] = run_cli(client, ["--json", BODY])
    assert result["output"] == "A, C, B, D"
    assert result["created"] is True


def test_repeat_reuses_cached_payload(client, transformer):
    results = run_cli(client, ["-r", "3", "-j", BODY])

    assert [r["created"] for r in results] == [True, False, False]
    assert len({r["id"] for r in results}) == 1
    assert len(transformer.calls) == 4  # only the first iteration reaches the transformer


def test_input_can_come_from_stdin(client):
    [result] = run_cli(client, ["-i", "-"], stdin=BODY)
    assert result["output"] == "A, C, B, D"


def test_input_can_come_from_file(client, tmp_path):
    path = tmp_path / "request.json"
    path.write_text(BODY)
    [result] = run_cli(client, ["--input", str(path)])
    assert result["output"] == "A, C, B, D"


def test_host_defaults_and_short_flag():
    assert str(parse_args(["-j", BODY]).host) == "http://localhost:8000/"
    assert str(parse_args(["-H", "http://example.com:9000", "-j", BODY]).host) == (
        "http://example.com:9000/"
    )


@pytest.mark.parametrize(
    "argv",
    [
        [],  # no input source
        ["-j", BODY, "-i", "-"],  # two input sources
        ["-j", BODY, "-r", "0"],  # non-positive repeat
        ["-j", BODY, "-H", "not a url"],
    ],
)
def test_invalid_arguments_are_rejected(argv):
    with pytest.raises(ValidationError):
        parse_args(argv)


def test_invalid_request_body_is_rejected(client):
    with pytest.raises(ValidationError):
        run_cli(client, ["-j", '{"list_1": ["a"], "list_2": []}'])


def test_settings_class_is_importable_without_side_effects():
    assert CliSettings.model_fields["repeat"].default == 1
