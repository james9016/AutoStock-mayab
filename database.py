import os
import socket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Host oficial transaccional de Supabase
DATABASE_URL = "postgresql://postgres.grnqhgctjjahvhkjckxa:AutoStockMayab2026@db.grnqhgctjjahvhkjckxa.supabase.co:5432/postgres"

# 2. Asegurar el driver postgresql:// correcto en Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. PARCHE DEFINITIVO DE RED: Forzamos la resolución de DNS estrictamente a IPv4
# Esto evita que Render intente usar IPv6 y devuelva "Network is unreachable".
original_getaddrinfo = socket.getaddrinfo

def forced_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Forzar AF_INET (IPv4) e ignorar AF_INET6
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = forced_ipv4_getaddrinfo

# 4. Inicializar motor optimizado para producción
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
