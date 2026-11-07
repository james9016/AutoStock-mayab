import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Intenta obtener la URL directa configurada en Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Si por alguna razón la variable está vacía, usamos la URL estricta corregida como respaldo automático
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@://supabase.com"

# Forzar compatibilidad de esquemas requerida por SQLAlchemy 2.0 y Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Crear el motor de conexión
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
