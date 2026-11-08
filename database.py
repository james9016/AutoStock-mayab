import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🔒 CONFIGURACIÓN DE RED: Conexión mediante el Pooler de Supabase (Puerto 6543) para compatibilidad IPv4 en Render
DEFAULT_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:6543/postgres?sslmode=require"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_URL)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
