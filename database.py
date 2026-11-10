import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # Usuario limpio sin puntos ni caracteres conflictivos
    u = "postgres"
    p = "AutoStockMayab2026"
    
    # IP numérica pública IPv4 de Supabase para la región us-east-1 (AWS)
    # Esto evita por completo el error de "Network is unreachable" de Render
    host_ip = "44.208.221.186"
    
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_ip}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        # 🔒 ESTA ES LA CLAVE: Forzamos al driver a enviar el ID del proyecto 
        # directamente en el handshake de Postgres, solucionando el SNI en IPv4
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
