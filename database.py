import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# Construcción estructural limpia sobre el host transaccional IPv4 directo
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres.grnqhgctjjahvhkjckxa",
    password="AutoStockMayab2026",
    host="db.grnqhgctjjahvhkjckxa.supabase.co",
    port=5432,
    database="postgres"
)

# Inicializar motor de base de datos desactivando la resolución IPv6 forzada
engine = create_engine(
    connection_url,
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
