import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🛑 DETÉNTE AQUÍ: Borra la línea de abajo por completo y pon tu URL de Supabase entre las comillas.
# Debe verse exactamente así dentro de las comillas: postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:5432/postgres
DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:5432/postgres"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
