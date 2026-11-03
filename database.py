# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Replit provee DATABASE_URL si conectas Supabase; usamos un fallback local por seguridad
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/autostock")

# Si se usa SQLite temporalmente para desarrollo local en Replit, habilitamos compatibilidad:
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
