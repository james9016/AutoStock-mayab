import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    url_conexion = DATABASE_URL
else:
    servidor = "aws-1-us-west-2" + ".pooler" + ".supabase" + ".com"
    url_conexion = URL.create(
        drivername="postgresql",
        username=os.getenv("DB_USER", "postgres.grnqhgctjjahvhkjckxa"),
        password=os.getenv("DB_PASSWORD", "AutoStockMayab2026"),
        host=servidor,
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "postgres")
    )

engine = create_engine(
    url_conexion,
    connect_args={"sslmode": "require"},
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
