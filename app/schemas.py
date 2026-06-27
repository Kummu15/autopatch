import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PatchRequest(BaseModel):
    repo_url: str
    issue_text: str
class PatchRunStartResponse(BaseModel):
    run_id: uuid.UUID
    status: str


class UserCreate(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PatchRunCreate(BaseModel):
    repo_id: str
    user_id: str
    issue_text: str
    model_used: Optional[str] = None


class EvalMetricOut(BaseModel):
    quality_score: Optional[float] = None
    tests_passed: Optional[int] = None
    tests_total: Optional[int] = None
    semantic_sim: Optional[float] = None
    latency_ms: Optional[int] = None

    class Config:
        from_attributes = True


class PatchRunOut(BaseModel):
    id: uuid.UUID
    status: str
    model_used: Optional[str] = None
    generated_diff: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    eval_metrics: Optional[EvalMetricOut] = None

    class Config:
        from_attributes = True
