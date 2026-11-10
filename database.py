import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # El usuario se mantiene limpio como 'postgres'
    u = "postgres"
    p = "AutoStockMayab2026"
    id_proyecto = "grnqhgctjjahvhkjckxa"
    
    # Host oficial del Pooler de Supabase compatible con arquitecturas IPv4 (AWS us-east-1)
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    # Puerto de sesión estándar del Pooler de Supabase
    puerto = "5432"
    base_datos = "postgres"
    
    # Pasamos el ID del proyecto directamente como opción de configuración en la URL
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
