# AutoPatch 🤖

An autonomous agentic AI system that generates, evaluates, and iterates on 
code patches — without human intervention.

**Live Demo:** [auto-patch-omega.vercel.app](https://auto-patch-omega.vercel.app)  
**API Docs:** [autopatch-b6ze.onrender.com/docs](https://autopatch-b6ze.onrender.com/docs)

---

## What It Does

AutoPatch takes a GitHub repository URL and a bug/issue description, then 
autonomously works through a six-stage agentic loop to produce a validated 
code patch:
Fetch → Plan → Generate → Eval → Reflect → Retry
The system reasons over its own outputs at each stage and decides whether 
to retry or commit — no human in the loop.

---

## Architecture

┌─────────────────────────────────────────────────┐

│                   Frontend                       │

│         (Vercel · Prism.js diff viewer)          │

└──────────────────────┬──────────────────────────┘

│ REST

┌──────────────────────▼──────────────────────────┐

│                  FastAPI Backend                  │

│              (Render · Python 3.12)              │

│                                                   │

│   POST /patch    GET /patch/{id}   GET /history  │

└──────┬───────────────────┬────────────────────── ┘

│                   │

┌──────▼──────┐    ┌───────▼────────┐

│  Groq LLM   │    │   PostgreSQL   │

│ llama-3.3   │    │  (4 tables)    │

│  -70b       │    │                │

└─────────────┘    └────────────────┘
---

## Agentic Loop

| Stage | What Happens |
|-------|-------------|
| **Fetch** | Pulls repository context and parses the issue |
| **Plan** | LLM reasons about what needs to change and why |
| **Generate** | Produces a candidate patch with full diff |
| **Eval** | Scores the patch across 3 metrics (see below) |
| **Reflect** | LLM reviews its own output and decides: commit or retry |
| **Retry** | If quality threshold not met, loops back with context |

---

## Evaluation Metrics

Each patch run persists real scores to PostgreSQL:

- `tests_passed` — whether the patch compiles and passes basic checks
- `semantic_sim` — embedding similarity between patch and issue intent
- `quality_score` — composite score combining correctness and clarity

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI · Python 3.12 |
| LLM | Groq · llama-3.3-70b-versatile |
| Database | PostgreSQL (normalized schema) |
| Auth | JWT · python-jose · passlib |
| Frontend | Vanilla JS · Prism.js · Dark theme |
| Deployment | Render (API) · Vercel (Frontend) |

---

## Database Schema

4 normalized tables:
users         — authenticated accounts

repos         — submitted repository targets

patch_runs    — agentic loop executions per repo/issue

eval_metrics  — per-run scores (tests_passed, semantic_sim, quality_score)
A repo can have many patch runs. Each patch run has exactly one eval result.
This decoupling means you can re-evaluate patches without re-generating them.

---

## API Endpoints
POST /patch          Submit a repo URL + issue → triggers agentic loop

GET  /patch/{id}     Check status and result of a specific run

GET  /history        List all past runs for the authenticated user

Full interactive docs: [autopatch-b6ze.onrender.com/docs](https://autopatch-b6ze.onrender.com/docs)

---

## Run Locally

```bash
git clone https://github.com/Kummu15/autopatch
cd autopatch
pip install -r requirements.txt

createdb autopatch
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/autopatch"
export GROQ_API_KEY="your-key"

uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` to test endpoints interactively.

---

## Key Design Decisions

- **Service layer decoupled from API layer** — swap models or eval logic 
  in `patch_service.py` without touching request handling in `main.py`
- **Normalized schema** — eval metrics stored separately from patch runs, 
  enabling independent re-scoring
- **Pinned to Python 3.12** — resolves pydantic/Python 3.14 incompatibility
- **Static Vercel deployment** — resolves serverless function incompatibility 
  via `vercel.json` configuration

---

## Built By

**Kumudhinisre Suresh**  
MS Computer Science — AI Specialization · University of Chicago  
[LinkedIn](https://linkedin.com/in/kumudhinisre-suresh-70136025a) · 
[GitHub](https://github.com/Kummu15)
