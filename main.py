import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Leemos directamente de las variables de entorno de Render para evitar hardcodear propiedades de red
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Respaldo de seguridad estricto con el formato oficial del Pooler de Sesión (Puerto 5432)
    # El usuario compuesto con el ID del proyecto garantiza el enrutamiento sin requerir SNI
    id_proyecto = "grnqhgctjjahvhkjckxa"
    DATABASE_URL = f"postgresql://postgres.{id_proyecto}:AutoStockMayab2026@://supabase.com"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require"
    },
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
