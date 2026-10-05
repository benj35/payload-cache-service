FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CACHE_DATABASE_URL=sqlite:////data/cache.db

WORKDIR /app

# Dependencies first so this layer is cached across source-only changes.
COPY pyproject.toml ./
RUN mkdir -p src/cache_service && touch src/cache_service/__init__.py \
    && pip install --no-cache-dir .
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

# Run unprivileged; /data holds the SQLite file and is meant to be a volume.
RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
USER app
VOLUME /data

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/docs')"
CMD ["uvicorn", "cache_service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
