import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app import models, schemas
from app.patch_service import generate_patch

app = FastAPI(title="AutoPatch API")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Allow your frontend (adjust origin for production)
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


@app.post("/patch", response_model=schemas.PatchRunOut)
def create_patch(request: schemas.PatchRequest, db: Session = Depends(get_db)):
    demo_user = db.query(models.User).first()
    if not demo_user:
        demo_user = models.User(email="demo@autopatch.dev", hashed_password="placeholder")
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)

    repo = (
        db.query(models.Repo)
        .filter(models.Repo.github_url == request.repo_url, models.Repo.user_id == demo_user.id)
        .first()
    )
    if not repo:
        repo = models.Repo(user_id=demo_user.id, github_url=request.repo_url)
        db.add(repo)
        db.commit()
        db.refresh(repo)

    patch_run = models.PatchRun(
        repo_id=repo.id,
        user_id=demo_user.id,
        issue_text=request.issue_text,
        status="running",
    )
    db.add(patch_run)
    db.commit()
    db.refresh(patch_run)

    try:
        result = generate_patch(request.repo_url, request.issue_text)
        patch_run.status = "success"
        patch_run.model_used = result["model_used"]
        patch_run.generated_diff = result["generated_diff"]
        patch_run.completed_at = datetime.utcnow()

        metric = models.EvalMetric(
            patch_run_id=patch_run.id,
            quality_score=result["quality_score"],
            latency_ms=result["latency_ms"],
        )
        db.add(metric)
        db.commit()
        db.refresh(patch_run)
    except Exception as e:
        patch_run.status = "failed"
        patch_run.error_message = str(e)
        patch_run.completed_at = datetime.utcnow()
        db.commit()

    return patch_run


@app.get("/patch/{patch_id}", response_model=schemas.PatchRunOut)
def get_patch(patch_id: uuid.UUID, db: Session = Depends(get_db)):
    patch_run = db.query(models.PatchRun).filter(models.PatchRun.id == patch_id).first()
    if not patch_run:
        raise HTTPException(status_code=404, detail="Patch run not found")
    return patch_run


@app.get("/history", response_model=list[schemas.PatchRunOut])
def get_history(db: Session = Depends(get_db)):
    return (
        db.query(models.PatchRun)
        .order_by(models.PatchRun.created_at.desc())
        .limit(50)
        .all()
    )
