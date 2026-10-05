"""Integration tests focused on minimising transformer calls."""


def post(client, list_1, list_2):
    response = client.post("/payload", json={"list_1": list_1, "list_2": list_2})
    assert response.status_code in (200, 201)
    return response.json()["id"]


def test_duplicate_strings_within_a_request_are_transformed_once(client, transformer):
    post(client, ["a", "a", "b"], ["b", "a", "a"])
    assert sorted(transformer.calls) == ["a", "b"]


def test_strings_cached_by_earlier_payloads_are_not_transformed_again(client, transformer):
    post(client, ["a", "b"], ["c", "d"])
    transformer.calls.clear()

    payload_id = post(client, ["a", "x"], ["d", "y"])

    assert sorted(transformer.calls) == ["x", "y"]
    assert client.get(f"/payload/{payload_id}").json() == {"output": "A, D, X, Y"}


def test_order_matters_for_payload_identity_but_not_for_the_string_cache(
    client, transformer
):
    first = post(client, ["a", "b"], ["c", "d"])
    transformer.calls.clear()
    second = post(client, ["c", "d"], ["a", "b"])

    assert first != second
    assert transformer.calls == []
    assert client.get(f"/payload/{second}").json() == {"output": "C, A, D, B"}


def test_inputs_that_only_differ_in_list_boundaries_do_not_collide(client):
    assert post(client, ["a, b"], ["c"]) != post(client, ["a"], ["b, c"])


def test_large_request_exceeds_sql_parameter_chunking(client, transformer):
    items = [f"s{i}" for i in range(1200)]
    payload_id = post(client, items, items)

    assert len(transformer.calls) == 1200
    assert client.get(f"/payload/{payload_id}").status_code == 200
