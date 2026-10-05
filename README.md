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

## Run

```bash
docker build -t payload-cache .
docker run --rm -p 8000:8000 -v payload-data:/data payload-cache
```

Locally:

```bash
pip install -e ".[dev]"
uvicorn cache_service.main:create_app --factory --reload
pytest
```

Configuration (env vars): `CACHE_DATABASE_URL` (default `sqlite:///./data/cache.db`),
`CACHE_TRANSFORM_LATENCY_SECONDS` (simulate a slow transformer, default `0`).

## CLI

```bash
cache-cli -H http://localhost:8000 -r 3 -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
cat request.json | cache-cli -i - -o results.jsonl
```

| Flag | Meaning |
|------|---------|
| `-H`, `--host` | Service URL (default `http://localhost:8000`) |
| `-r`, `--repeat` | Number of POST+GET iterations (default `1`) |
| `-i`, `--input` | File with the JSON body, `-` for stdin |
| `-j`, `--json` | JSON body inline (exactly one of `-i`/`-j` is required) |
| `-o`, `--output` | Result file, `-` for stdout (default) |

Each iteration prints one JSON line: `id`, `created`, `output`, `elapsed_ms`.
With `CACHE_TRANSFORM_LATENCY_SECONDS=0.2` on the server, `--repeat` makes the
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
