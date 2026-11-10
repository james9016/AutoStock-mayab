import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # El usuario debe ser estrictamente 'postgres' para evitar fallos de autenticación
    u = "postgres"
    p = "AutoStockMayab2026"
    
    # Usamos el host del pooler regional sobre el puerto de sesión para mantener compatibilidad IPv4
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    # Puerto de sesión estándar (Permite operaciones de creación de tablas en el startup)
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        # 💡 SOLUCIÓN DEFINITIVA: Inyecta el ID de forma explícita en los parámetros de inicialización
        # del driver de Postgres. Esto sustituye la falta de SNI y enruta la petición de inmediato.
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
