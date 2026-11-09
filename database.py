import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # Parámetros directos clásicos de Supabase
    u = "postgres"
    p = "AutoStockMayab2026"
    
    # Reconstrucción del subdominio directo clásico de tu base de datos
    id_proyecto = "grnqhgctjjahvhkjckxa"
    h1 = "db"
    h2 = "supabase"
    h3 = "co"
    host_completo = f"{h1}.{id_proyecto}.{h2}.{h3}"
    
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require"
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
