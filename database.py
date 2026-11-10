import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Leemos directamente la variable de entorno segura configurada en Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Si no existe la variable en local, usa el pooler compartido como respaldo
if not DATABASE_URL:
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  
    p = "AutoStockMayab2026"
    host_pooler = "://supabase.com"
    puerto = "5432"
    base_datos = "postgres"
    DATABASE_URL = f"postgresql://{u}:{p}@{host_pooler}:{puerto}/{base_datos}"

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
