# Document Copilot

An internal AI chatbot that lets analysts query a corpus of documents in plain English and get sourced, citable answers.

## The client

**Driftwood Capital** — fictional independent investment research firm. Their analysts spend half their week reading 10-Ks and 10-Qs before they can produce any original analysis. Document Copilot eats that intake work so they can skip straight to insight.

Full brief: [docs/client-brief.md](docs/client-brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Docker Compose or Railway                            |
| LLM + embeddings   | DeepSeek chat + DashScope embeddings via OpenAI SDK   |

## Repo layout

```text
document-copilot/
├── AGENTS.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── client-brief.md # the client one-pager
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + `data/download.py` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 20+ (LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then configure separate [DeepSeek](https://platform.deepseek.com/) chat and [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/get-api-key) embedding keys.

## Self-hosting with Docker Compose

From the repository root, copy `.env.example` to `.env` and fill in the two public Supabase values. The [root Dockerfile](Dockerfile) builds React and copies the static files into the Python image. Uvicorn serves React at `/` and the FastAPI endpoints under `/api` in the same container.

Configure `backend/.env` as described below for database and model access. React receives only the public Supabase settings at build time. The default host binding is `127.0.0.1:8000` over HTTP. For public HTTPS, either use an existing HTTPS entry point or configure a certificate and key directly in Uvicorn.

```bash
docker compose config --quiet
docker compose build
docker compose run --rm --no-deps app alembic current
# If the target database is behind, apply migrations before starting the app:
# docker compose run --rm --no-deps app alembic upgrade head
docker compose up -d
```

Open `http://127.0.0.1:8000` and check `/api/health`. Set `APP_PORT` to use a different host port. To rebuild after changing a frontend setting, run `docker compose up -d --build`.

## Running locally

Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md), then create env files for both services.

Backend env:

```bash
cd backend
cp .env.example .env
```

Fill these values in `backend/.env`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` using the direct Supabase Postgres connection, not the transaction pooler
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (DeepSeek chat endpoint; the variable names refer to the compatible SDK)
- `EMBEDDING_API_KEY` (DashScope key, separate from the chat key)
- `EMBEDDING_BASE_URL` (endpoint for the key's workspace and region)
- `ALLOWED_ORIGINS=http://localhost:5173`

The default embedding model is `text-embedding-v4`, with `EMBEDDING_DIMENSIONS=1536` and `EMBEDDING_BATCH_SIZE=10`. Ingestion and query embedding share these settings. Changing models requires rebuilding existing vectors even when their dimensions match.

Frontend env:

```bash
cd frontend
cp .env.example .env
```

Fill these values in `frontend/.env`:

- `VITE_API_BASE_URL=http://localhost:8000`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Install dependencies and migrate the database:

```bash
cd backend
uv sync
uv run alembic upgrade head

cd ../frontend
pnpm install
```

Run the backend:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Run the frontend in another terminal:

```bash
cd frontend
pnpm dev
```

Open the Vite URL, usually `http://localhost:5173`.

Useful checks:

```bash
cd backend
uv run pytest -m "not integration"
uv run ruff check .
uv run python scripts/smoke_retrieval.py

cd ../frontend
pnpm lint
pnpm build
```

## Sample SEC data

Use the standalone downloader to fetch a small local 10-K sample from SEC EDGAR. Edit the params at the top of `data/download.py`, especially `USER_AGENT`, then run:

```bash
uv run data/download.py
```

By default this downloads the latest 5 10-K filings for AAPL, MSFT, NVDA, AMZN, and GOOGL into year folders under `data/downloads/` and writes a `manifest.json`.
Downloaded files are gitignored; the `data/` folder itself stays in git for the script and notes.

Convert downloaded HTML filings to Markdown:

```bash
uv run data/convert_to_markdown.py
```

Load filing metadata into Supabase:

```bash
cd backend
uv sync --extra ingest
uv run python -m ingest.load_source_documents
```

Chunk and embed the full sample corpus:

```bash
cd backend
uv run python -m ingest.chunk_and_embed --all
```

Update an existing corpus:

```bash
# Re-run metadata loading; existing rows are skipped by default.
cd backend
uv run python -m ingest.load_source_documents

# Ingest only new filings; existing chunks are skipped by default.
uv run python -m ingest.chunk_and_embed --all
```

Force-refresh chunks for one filing after changing chunking logic:

```bash
cd backend
uv run python -m ingest.chunk_and_embed --accession 0000000000-00-000000 --force
```
