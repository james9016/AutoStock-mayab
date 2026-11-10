import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # El usuario debe ser estrictamente 'postgres' para evitar el error FATAL
    u = "postgres"
    p = "AutoStockMayab2026"
    id_proyecto = "grnqhgctjjahvhkjckxa"
    
    # Servidor del Pooler regional correspondiente a us-east-1
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "5432"
    base_datos = "postgres"
    
    # Inyectamos el ID del proyecto a través de las opciones nativas de PostgreSQL (?options=-c project=...)
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}?options=-c%20project={id_proyecto}"

DATABASE_URL = obtener_url_segura()

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
