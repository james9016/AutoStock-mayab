import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 ESTÁNDAR OBLIGATORIO PARA IPv4: Concatenar el ID con un punto en el usuario
    # apuntando estrictamente al puerto del pooler transaccional 6543
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  
    p = "AutoStockMayab2026"
    
    # Host oficial del Pooler regional de Supabase
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    puerto = "6543" 
    base_datos = "postgres"
    
    # Forzamos la desactivación de prepared statements en el string de conexión de SQLAlchemy
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}?prepare_threshold=0"

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
