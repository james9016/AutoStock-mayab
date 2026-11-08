import os
import socket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Host directo de tu proyecto (Supabase resuelve automáticamente tu región)
DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:5432/postgres"

# 2. Forzar compatibilidad de esquemas de drivers en Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. TRUCO DE RED: Obligamos al conector a usar únicamente IPv4 (Evita el 'Network is unreachable')
# Render gratuito no tiene IPv6, por lo que este parche previene caídas de red.
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        "gssencmode": "disable",
        "options": "-c client_encoding=utf8"
    },
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
