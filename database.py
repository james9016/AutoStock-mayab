import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Dirección de conexión directa corregida sin separación de variables
DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@://supabase.com"

# Forzar el driver correcto compatible con SQLAlchemy 2.x e inyecciones de Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Inicializar motor de base de datos estable
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}, 
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
