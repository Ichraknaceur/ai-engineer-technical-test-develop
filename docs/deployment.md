# Deployment

---

## Prerequisites

- Docker & Docker Compose v2
- `uv` — [install](https://docs.astral.sh/uv/)
- An OpenAI API key

---

## First-time setup

```sh
make bootstrap
```

This will:
1. Copy `.env.example` → `.env` (fill in your `ANTHROPIC_API_KEY`)
2. Build Docker images
3. Run database migrations

Then start all services:

```sh
make up
```

| Service | URL |
|---|---|
| Frontend (UI) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

---

## Docker Compose services

| Service | Image | Port |
|---|---|---|
| `backend` | `./backend` | 8000 |
| `worker` | `./backend` (Celery) | — |
| `frontend` | `./frontend` | 3000 |
| `postgres` | `postgres:16-alpine` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — |
| `DATABASE_URL` | Yes | set in docker-compose |
| `REDIS_URL` | Yes | set in docker-compose |
| `MAX_PAGES_PER_QUARRY` | No | `5` |
| `BASE_SCRAPE_DELAY_S` | No | `1.0` |
| `LOG_LEVEL` | No | `INFO` |

---

## Run an extraction from the CLI

```sh
make extract LAT=48.8566 LON=2.3522 RADIUS_KM=50
```

---

## Documentation

```sh
make docs-serve    # preview locally at http://localhost:8090
make docs-deploy   # deploy to GitHub Pages
```

!!! note "GitHub Pages setup"
    `make docs-deploy` uses `mkdocs gh-deploy`, which pushes the built site to the
    `gh-pages` branch of your repository. Enable GitHub Pages in your repo settings
    (Settings → Pages → Branch: `gh-pages`).
