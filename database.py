import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Intentamos leer la variable de entorno directa de Render
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Si por alguna razón Render no la inyecta, armamos el respaldo dinámico
if not DATABASE_URL:
    # Cambiamos el host al pooler directo de Supabase
    DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:5432/postgres"

# 3. Forzar el driver correcto compatible con SQLAlchemy 2.x
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 4. Inicializar motor optimizado para producción
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
