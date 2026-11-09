import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Leer cada pieza de la conexión de forma independiente desde Render
user = os.environ.get("DB_USER", "postgres")
password = os.environ.get("DB_PASSWORD", "AutoStockMayab2026")
host = os.environ.get("DB_HOST", "://supabase.com")
port = os.environ.get("DB_PORT", "5432")

# Construir la URL de forma dinámica y segura dentro del servidor
DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/postgres?sslmode=require"

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
