import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # Mantener el usuario base estricto para la autenticación directa
    u = "postgres"
    p = "AutoStockMayab2026"
    
    # Host e infraestructura de Supabase correspondiente a la región us-east-1
    id_proyecto = "grnqhgctjjahvhkjckxa"
    host_directo = f"db.{id_proyecto}.supabase.co"
    
    # Puerto de sesión estándar (Permite operaciones DDL como create_all)
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_directo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        # Inyección forzada del ID del proyecto en las opciones de inicialización del driver
        "options": "-c project=grnqhgctjjahvhkjckxa"
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
