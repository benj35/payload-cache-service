SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


def test_create_then_read_returns_interleaved_transformed_output(client):
    created = client.post("/payload", json=SAMPLE)
    assert created.status_code == 201

    read = client.get(f"/payload/{created.json()['id']}")
    assert read.status_code == 200
    assert read.json() == {"output": SAMPLE_OUTPUT}


def test_same_input_reuses_identifier_and_skips_transformer(client, transformer):
    first = client.post("/payload", json=SAMPLE)
    calls_after_first = len(transformer.calls)
    second = client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(transformer.calls) == calls_after_first


def test_different_input_gets_different_identifier(client):
    other = {"list_1": ["a"], "list_2": ["b"]}
    assert client.post("/payload", json=SAMPLE).json()["id"] != (
        client.post("/payload", json=other).json()["id"]
    )


def test_unknown_identifier_returns_404(client):
    assert client.get("/payload/does-not-exist").status_code == 404


def test_mismatched_list_lengths_are_rejected(client):
    response = client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c"]})
    assert response.status_code == 422


def test_empty_lists_are_rejected(client):
    assert client.post("/payload", json={"list_1": [], "list_2": []}).status_code == 422
