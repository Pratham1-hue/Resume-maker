# Quick Resume Maker

AI-powered resume tailor: ingest a candidate profile once, align it to any job
description, export a polished resume.

## How to Run

> **Note (Oct 2026): Docker files were removed** (`docker-compose.yml`,
> `backend/Dockerfile`, `frontend/Dockerfile`) because the app runs locally.
> They can be recreated on request — the last known-good contents used
> `python:3.12-slim` + local deps install for the backend and `node:20-alpine`
> for the frontend, with ports 8000 (API) and 3000→5173 (UI).
>
> **Important: install from the project root, run from `backend/`.**
> `pyproject.toml` lives at the project root, so `pip install -e .` must be run
> from `quick-resume-maker/`, NOT from `quick-resume-maker/backend/`.
> The server itself runs from `backend/` so that `import app...` resolves.

### Local development

**1. Backend**

```powershell
# from quick-resume-maker/
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

Stop with `Ctrl+C`, then `docker-compose down`.

### Option B — Local development

**1. Backend**

```powershell
cd quick-resume-maker

# create + activate a venv (Windows)
python -m venv .venv
.venv\Scripts\activate

# install from the PROJECT ROOT (this is the step people get wrong)
python -m pip install -e .

# run from the backend/ directory
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**2. Frontend** (new terminal, venv not needed)

```powershell
cd quick-resume-maker\frontend
npm install
npm run dev -- --host
```

- Frontend: http://localhost:5173 (Vite default)
- It calls the backend at http://localhost:8000 (override with
  `VITE_API_BASE_URL` in a `frontend/.env` file if needed).

**3. Environment variables** (project root)

```powershell
copy .env.example .env
# then edit .env:
#   ANTHROPIC_API_KEY=...   # required for Align (Claude, default provider)
#   GEMINI_API_KEY=...      # alternative: set LLM_PROVIDER=gemini
#   GITHUB_TOKEN=...        # optional: raises GitHub rate limit 60 -> 5000/hr
```

Without an LLM key the app still starts, ingestion still works, and the JD
parser falls back to keyword heuristics — only the Align step needs a key.

### Typical flow

1. Open the frontend, fill the profile form (name, email, GitHub username) →
   ingestion starts automatically and polls `GET /api/v1/profiles/{id}/ingest/status`.
2. When status is `completed`, paste a job description (min 50 chars) → Generate.
3. Download the result as DOCX or PDF (both generated locally; no extra tools needed).

Direct API equivalents:

```bash
POST /api/v1/profiles/                        # create profile
GET  /api/v1/profiles/{id}/ingest/status      # poll ingestion
POST /api/v1/profiles/{id}/ingest             # (re-)start ingestion
POST /api/v1/align/                           # {profile_id, title, raw_text, ...}
POST /api/v1/export/                          # {profile_id, job_title, format}
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip install -e .` → "neither setup.py nor pyproject.toml found" | ran from `backend/` | run it from the project root |
| `uvicorn` → `ModuleNotFoundError: No module named 'app'` | ran from project root | `cd backend` first, then run uvicorn |
| `email-validator is not installed` | old install | `python -m pip install -e .` again (pyproject now includes it) |
| `No module named 'soxr'` | transformers audio dep | reinstall from updated pyproject (includes `soxr`) |
| Align returns 400 "not yet ingested" | ingestion still running/failed | wait for `completed`, or check `error` in the status payload |
| Align returns 500 mentioning API key | no LLM key set | add `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY` + `LLM_PROVIDER=gemini`) to `.env` and restart |
| Port 8000/5173 busy | old server still running | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |

## Architecture

```
quick-resume-maker/
├── pyproject.toml          # backend deps + build config (install from here)
├── .env.example            # copy to .env, add API keys
├── backend/
│   └── app/
│       ├── main.py         # FastAPI app; routers included directly
│       ├── config.py       # pydantic-settings (all defaults, .env optional)
│       ├── api/            # profiles / ingest / align / export
│       ├── schemas/        # Pydantic models (resume.py is canonical for resumes)
│       ├── ingestion/      # GitHub REST client, portfolio scraper, chunker
│       ├── rag/            # local embeddings, Chroma (1 collection/profile), MMR retriever, JD parser
│       ├── llm/            # provider client (Anthropic/Gemini), aligner, verifier
│       └── export/         # DOCX renderer (template + built-in fallback layout)
└── frontend/               # Vite + React SPA (NOT Next.js; old app/ pages are unused)
    ├── vite.config.js      # host:true, port 5173
    ├── postcss.config.js   # tailwind + autoprefixer
    └── src/
        ├── main.jsx        # entry (see index.html script tag)
        ├── App.jsx         # profile → ingest → align → export flow
        └── lib/api-client.ts  # single "/api/v1" prefix, snake_case mapping
```

Key design points:

- **Provenance**: every chunk has a `chunk_id`; every bullet cites `source_chunk_ids`.
- **Two passes**: Align (LLM) → Verifier (deterministic grounding check; LLM re-check optional).
- **One Chroma collection per profile**; re-ingest overwrites it.
- **Local embeddings** (`all-MiniLM-L6-v2`) — no key needed; first run downloads the model once.
- **JD parser** uses the LLM when a key exists, otherwise a keyword heuristic.
- **DOCX export** tries `backend/app/export/templates/resume_classic.docx`, else a built-in python-docx layout (the checked-in file is a placeholder, not a valid template — the fallback is intentional).
- **Frontend speaks snake_case** to match the API (no camelCase aliases configured).
