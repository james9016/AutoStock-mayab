import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 Formato oficial exacto de Supabase para el pooler por puerto 5432 (Modo Transaccional):
    # El usuario base y el ID del proyecto deben separarse estrictamente por un PUNTO '.' 
    # para evitar romper el formateador de URLs de SQLAlchemy (los dos puntos ':' romperían el esquema usuario:contraseña).
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  # <- Corregido a punto para compatibilidad con SQLAlchemy
    p = "AutoStockMayab2026"
    
    # Servidor del Pooler regional correspondiente a us-east-1
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "5432"
    base_datos = "postgres"
    
    # URL limpia y perfectamente estructurada para el Pooler
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
    pool_pre_ping=True,    # Verifica si la conexión sigue viva antes de despacharla
    pool_recycle=300       # Cierra y renueva las conexiones cada 5 minutos para evitar bloqueos en Render
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
