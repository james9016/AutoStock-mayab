import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 EL TRUCO DEFINITIVO: Unimos el usuario 'postgres' y el ID del proyecto usando suma de textos.
    # Esto genera exactamente 'postgres.grnqhgctjjahvhkjckxa', que es lo que exige Supabase.
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = "postgres" + "." + id_proyecto
    p = "AutoStockMayab2026"
    
    # Servidor del Pooler regional correspondiente a us-east-1 (Puerto de sesión estándar 5432)
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
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
