import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Intentar obtener la URL desde las variables de Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Si no existe en Render, armamos el respaldo estricto
if not DATABASE_URL:
    DB_USER = "postgres.grnqhgctjjahvhkjckxa"
    DB_PASS = "AutoStockMayab2026"
    DB_HOST = "://supabase.com"
    DB_PORT = "6543"
    DB_NAME = "postgres"
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Asegurar compatibilidad de drivers en Render si inicia con 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Crear motor de base de datos optimizado
engine = create_engine(
    DATABASE_URL, 
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
