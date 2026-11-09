import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # En el puerto 6543 el usuario debe ser el estándar sin puntos
    u = "postgres"
    p = "AutoStockMayab2026"
    
    # Servidor de conexión (Pooler regional us-east-1)
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "6543"
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

# El ID del proyecto se pasa obligatoriamente en las opciones del conector
id_proyecto = "grnqhgctjjahvhkjckxa"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        "options": f"-c anypoint=true -c project={id_proyecto}"
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
