import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # Estructura transaccional limpia para el puerto 6543
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  
    p = "AutoStockMayab2026"
    
    # Host global del Pooler de Supabase compatible con IPv4
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "6543" 
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        # 💡 Solución definitiva para psycopg2 con Supavisor en modo transaccional:
        # Desactiva los cursores del lado del servidor para evitar conflictos DDL en el startup
        "server_side_cursors": False
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
