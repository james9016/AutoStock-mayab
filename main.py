import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 REGLA DE INFRAESTRUCTURA DE SUPABASE PARA REDES IPv4 COMPLETAMENTE GRATUITA:
    # Concatenamos el ID del proyecto al usuario separado por un punto.
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  
    p = "AutoStockMayab2026"
    
    # HOST CORRECTO: Pooler oficial de AWS us-east-1 (Resuelve el tráfico IPv4 en Render)
    host_pooler = "aws-0-us-east-1.pooler.supabase.com"
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_pooler}:{puerto}/{base_datos}"

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
