import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Creamos la URL desglosada de forma estricta como un objeto de SQLAlchemy
# Esto obliga al sistema a leer el puerto como un número entero real (6543)
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres.grnqhgctjjahvhkjckxa",
    password="AutoStockMayab2026",
    host="://supabase.com",
    port=6543,
    database="postgres"
)

# 2. Inicializar el motor de la base de datos usando la URL estructural segura
engine = create_engine(
    connection_url,
    connect_args={"sslmode": "require"}, # Requerido para la seguridad de Supabase
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
