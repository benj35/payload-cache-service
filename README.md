# Payload caching service

FastAPI microservice that builds payloads from two string lists via an external
"transformer function" (simulated: upper-casing) and caches everything it can,
so the transformer is called as rarely as possible.

## How it works

`POST /payload` takes `list_1` and `list_2` (same length, 1–10 000 items) and
returns the identifier of the payload: the transformed strings interleaved
(`l1[0], l2[0], l1[1], …`) and joined with `", "`. `GET /payload/{id}` returns
`{"output": "..."}`.

Transformer calls are minimised on two levels:

1. **Payload identity** – the id is the SHA-256 of the canonical JSON of the
   input. The same input always yields the same id and is answered straight from
   the database (`200` instead of `201`, no transformer calls).
2. **Per-string cache** – each transformed string is stored in SQLite. A new
   payload only transforms strings never seen before, and each distinct string
   once, even if repeated within the request or across lists.

Concurrent writes of the same row are resolved with `INSERT … ON CONFLICT DO
NOTHING`, so racing requests cannot fail each other.

## Run (Docker)

Docker is the supported way to run the service, the tests and the CLI; no local
Python setup is needed.

```bash
docker build -t payload-cache .
docker run -d --name payload-cache -p 8000:8000 -v payload-data:/data payload-cache
```

The API is then at <http://localhost:8000> (interactive docs at `/docs`). The
SQLite file lives in the `payload-data` volume, so data survives restarts.
Stop and remove with `docker rm -f payload-cache`.

Configuration (env vars, pass with `-e`): `CACHE_DATABASE_URL` (default in the
image: `sqlite:////data/cache.db`) and `CACHE_TRANSFORM_LATENCY_SECONDS`
(simulates a slow transformer, default `0`).

Quick check:

```bash
curl -X POST localhost:8000/payload -H 'content-type: application/json' \
  -d '{"list_1": ["first string", "second string"], "list_2": ["other string", "another string"]}'
curl localhost:8000/payload/<id from the response>
```

## Tests

```bash
docker run --rm -v "$PWD":/app -w /app python:3.12-slim \
  sh -c 'pip install -q -e ".[dev]" && pytest -v'
```

## CLI

The CLI (`cache-cli`) is installed in the image and talks to the service over
HTTP. With the container above running:

```bash
docker exec payload-cache cache-cli -r 3 -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
docker exec -i payload-cache cache-cli -i - < request.json
docker exec payload-cache cache-cli --help
```

| Flag | Meaning |
|------|---------|
| `-H`, `--host` | Service URL (default `http://localhost:8000`) |
| `-r`, `--repeat` | Number of POST+GET iterations (default `1`) |
| `-i`, `--input` | File with the JSON body, `-` for stdin |
| `-j`, `--json` | JSON body inline (exactly one of `-i`/`-j` is required) |
| `-o`, `--output` | Result file, `-` for stdout (default) |

Each iteration prints one JSON line: `id`, `created`, `output`, `elapsed_ms`.
Start the container with `-e CACHE_TRANSFORM_LATENCY_SECONDS=0.5` to make the
cache visible: the first iteration is slow, the rest are fast.

## Decisions and shortcuts

- **`-h` clash**: the task lists `-h` for both `--host` and `--help`. `-h` stays
  help (standard), host uses `-H`.
- **Sync endpoints + sync SQLAlchemy**: the transformer and driver are blocking;
  FastAPI runs `def` endpoints in a thread pool. Async would need an async
  driver and an async transformer client for no gain here.
- **No single-flight**: two simultaneous requests with the same *new* string may
  both call the transformer once. Preventing that needs per-key locking (or a
  shared lock service when scaled out); results stay correct either way.
- **`create_all` instead of migrations**, and the string itself as primary key
  (see the note in `models.py` for PostgreSQL).
- **Empty lists are rejected** (422): they would produce an empty payload that
  is almost certainly a client bug.
- Payloads and cached strings are never evicted.
