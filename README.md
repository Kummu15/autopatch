# AutoPatch — Project Scaffold

## What's here
- `schema.sql` — raw Postgres schema (4 tables: users, repos, patch_runs, eval_metrics)
- `app/models.py` — SQLAlchemy ORM models matching the schema
- `app/database.py` — DB connection (reads `DATABASE_URL` env var)
- `app/schemas.py` — Pydantic request/response models
- `app/patch_service.py` — where your real Groq pipeline plugs in (currently has a placeholder prompt + scorer — **replace with your actual eval logic**)
- `app/main.py` — FastAPI app with 3 endpoints:
  - `POST /patch` — submit a repo URL + issue, get back a generated patch + score
  - `GET /patch/{id}` — check status/result of a specific run
  - `GET /history` — list past runs (this becomes your "history portal" page)

## To run locally
```bash
pip install -r requirements.txt
createdb autopatch   # requires local Postgres
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/autopatch"
export GROQ_API_KEY="your-key"
uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` to test endpoints interactively (this is still localhost — not a substitute for the deployed link).

## Next steps, in order
1. **Plug in your real Groq pipeline** in `patch_service.py` — replace the placeholder prompt and `score_patch()` with your actual eval logic from the AutoPatch research work.
2. **Add real auth** (this scaffold uses a single demo user as a placeholder — fine for now, but you'll want JWT or AWS Cognito before this counts as "production").
3. **Deploy Postgres on AWS RDS** — create a free-tier instance, point `DATABASE_URL` at it.
4. **Deploy the API** — Elastic Beanstalk is the fastest path for FastAPI on AWS; EC2 + gunicorn/uvicorn is more "from scratch" if you want that on your resume.
5. **Build the frontend** — one page: submit form → polling/status → diff viewer + score. Deploy to Vercel.
6. **Point a real domain at both.**

## Why this structure
- Service logic (`patch_service.py`) is decoupled from the API layer (`main.py`) — you can swap models or eval logic without touching request handling.
- Schema is normalized: a repo can have many patch runs, each patch run has one eval result — this is the kind of design decision you should be ready to explain in an interview.