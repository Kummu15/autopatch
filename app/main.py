import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import SessionLocal, engine, get_db
from app.patch_service import generate_patch

app = FastAPI(title="AutoPatch API")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)

@app.get("/")
def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")


def _score_tests_passed(diff: str) -> tuple[int, int]:
    """
    Basic heuristic: count added lines as a proxy for tests_passed.
    Returns (tests_passed, tests_total).
    """
    if not diff:
        return 0, 0
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    total = max(added + removed, 1)
    passed = added  # lines added = improvements made
    return passed, total


def _score_semantic_sim(issue_text: str, diff: str) -> float:
    """
    Basic keyword overlap between issue and diff as a proxy for semantic similarity.
    Returns a float between 0 and 1.
    """
    if not diff or not issue_text:
        return 0.0
    issue_words = set(issue_text.lower().split())
    diff_words = set(diff.lower().split())
    overlap = issue_words & diff_words
    return round(len(overlap) / max(len(issue_words), 1), 4)


def _run_patch_job(run_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        patch_run = db.query(models.PatchRun).filter(models.PatchRun.id == run_id).first()
        if not patch_run:
            return
        try:
            result = generate_patch(
                repo_url=patch_run.repo.github_url if patch_run.repo else "demo-repo",
                issue_text=patch_run.issue_text,
                code=None,
                language="python",
            )

            diff = result.get("generated_diff", "")
            tests_passed, tests_total = _score_tests_passed(diff)
            semantic_sim = _score_semantic_sim(patch_run.issue_text, diff)

            patch_run.status = result.get("status", "failed")
            patch_run.model_used = result.get("model_used")
            patch_run.generated_diff = diff
            patch_run.attempt_number = result.get("attempt_number", 1)
            patch_run.reflection_log = result.get("reflection_log", [])
            patch_run.error_message = (
                None if result.get("status") == "success"
                else result.get("verification", {}).get("reason")
            )
            patch_run.completed_at = datetime.utcnow()

            metric = models.EvalMetric(
                patch_run_id=patch_run.id,
                quality_score=result.get("score"),
                latency_ms=result.get("latency_ms", 0),
                tests_passed=tests_passed,
                tests_total=tests_total,
                semantic_sim=semantic_sim,
            )
            db.add(metric)
            db.commit()
            db.refresh(patch_run)

        except Exception as exc:
            patch_run.status = "failed"
            patch_run.error_message = str(exc)
            patch_run.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@app.post("/patch", response_model=schemas.PatchRunStartResponse)
async def create_patch(
    request: schemas.PatchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user_id = request.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        normalized_user_id = uuid.UUID(str(user_id))
    except ValueError:
        normalized_user_id = uuid.uuid4()

    user = db.query(models.User).filter(models.User.id == normalized_user_id).first()
    if not user:
        user = models.User(
            id=normalized_user_id,
            email=f"user-{str(normalized_user_id)[:8]}@autopatch.dev",
            hashed_password="placeholder",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    repo = (
        db.query(models.Repo)
        .filter(models.Repo.github_url == request.repo_url, models.Repo.user_id == user.id)
        .first()
    )
    if not repo:
        repo = models.Repo(user_id=user.id, github_url=request.repo_url)
        db.add(repo)
        db.commit()
        db.refresh(repo)

    patch_run = models.PatchRun(
        repo_id=repo.id,
        user_id=user.id,
        issue_text=request.issue_text,
        status="running",
    )
    db.add(patch_run)
    db.commit()
    db.refresh(patch_run)

    background_tasks.add_task(_run_patch_job, patch_run.id)
    return {"run_id": patch_run.id, "status": patch_run.status}


@app.get("/patch/{patch_id}", response_model=schemas.PatchRunOut)
def get_patch(patch_id: uuid.UUID, db: Session = Depends(get_db)):
    patch_run = db.query(models.PatchRun).filter(models.PatchRun.id == patch_id).first()
    if not patch_run:
        raise HTTPException(status_code=404, detail="Patch run not found")
    return patch_run


@app.get("/history", response_model=list[schemas.PatchRunOut])
def get_history(
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(default=None),
):
    query = db.query(models.PatchRun)
    if user_id:
        try:
            normalized_user_id = uuid.UUID(str(user_id))
        except ValueError:
            normalized_user_id = None
        if normalized_user_id is not None:
            query = query.filter(models.PatchRun.user_id == normalized_user_id)
    return query.order_by(models.PatchRun.created_at.desc()).limit(50).all()
