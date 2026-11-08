import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Host corregido apuntando al Pooler con puerto 6543 para saltar el bloqueo de red
DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@://supabase.com"

# Forzar el esquema correcto compatible con SQLAlchemy 2.x
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Inicializar motor de base de datos estable
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
