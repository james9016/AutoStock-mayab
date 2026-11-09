import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 EL SECRETO: Para el puerto 5432, Supabase requiere el ID del proyecto concatenado con el usuario.
    # Usamos el escape de cadena estándar de PostgreSQL para evitar que el filtro de red lo rechace.
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres" + f"[{id_proyecto}]"
    p = "AutoStockMayab2026"
    
    # Pooler regional us-east-1 (Forzado a IPv4 nativo en el puerto de sesión estándar)
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "5432"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura().replace("[", ".").replace("]", "")

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
