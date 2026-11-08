import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# Construcción estructural con IP IPv4 directa para saltar el bloqueo de red de Render
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres.grnqhgctjjahvhkjckxa",
    password="AutoStockMayab2026",
    host="44.216.29.125",  # <-- IP IPv4 directa de tu base de datos
    port=5432,
    database="postgres"
)

# Inicializar motor de base de datos estable
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
