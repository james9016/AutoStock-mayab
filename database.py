import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# Construcción modular con el host correcto asignado a tu ID de proyecto en Supabase
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres.grnqhgctjjahvhkjckxa",
    password="AutoStockMayab2026",
    host="://supabase.com",  # <-- Tu servidor real del Pooler de Supabase
    port=6543,                                    # <-- Puerto transaccional obligatorio
    database="postgres"
)

# Inicializar motor de base de datos optimizado para producción en Render
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
    """Dependencia de FastAPI para control transaccional seguro e inyección"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
