import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🚀 URL IPv4 CORRECTA: Conexión directa al Pooler transaccional en el puerto 6543
DEFAULT_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@://supabase.com"
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
