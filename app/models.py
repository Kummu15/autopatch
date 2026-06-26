import uuid

from sqlalchemy import Column, String, Text, Integer, Numeric, ForeignKey, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    repos = relationship("Repo", back_populates="owner", cascade="all, delete-orphan")


class Repo(Base):
    __tablename__ = "repos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    github_url = Column(String(500), nullable=False)
    default_branch = Column(String(100), default="main")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="repos")
    patch_runs = relationship("PatchRun", back_populates="repo", cascade="all, delete-orphan")


class PatchRun(Base):
    __tablename__ = "patch_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    issue_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    model_used = Column(String(100))
    generated_diff = Column(Text)
    error_message = Column(Text)
    attempt_number = Column(Integer, nullable=False, default=1)
    reflection_log = Column(JSONB, default=list)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))
    repo = relationship("Repo", back_populates="patch_runs")
    eval_metrics = relationship("EvalMetric", back_populates="patch_run", uselist=False)


class EvalMetric(Base):
    __tablename__ = "eval_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patch_run_id = Column(UUID(as_uuid=True), ForeignKey("patch_runs.id", ondelete="CASCADE"), nullable=False)
    quality_score = Column(Numeric(5, 2))
    tests_passed = Column(Integer)
    tests_total = Column(Integer)
    semantic_sim = Column(Numeric(5, 4))
    latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    patch_run = relationship("PatchRun", back_populates="eval_metrics")
