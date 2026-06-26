import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# On AWS, set this to your RDS Postgres connection string, e.g.:
# postgresql://user:password@your-db.xxxxx.us-east-1.rds.amazonaws.com:5432/autopatch
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/autopatch"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()