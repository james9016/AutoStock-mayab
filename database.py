import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Credenciales por defecto (Corregidas con 'kxa' al final)
DB_USER = "postgres.grnqhgctjjahvhkjckxa"
DB_PASS = "AutoStockMayab2026"

PARTE_AWS = "aws-1-us-west-2"
PARTE_POOLER = "pooler"
PARTE_SUPABASE = "supabase"
DB_HOST = f"{PARTE_AWS}.{PARTE_POOLER}.{PARTE_SUPABASE}.com"
DB_PORT = "6543"
DB_NAME = "postgres"

# URL base por si no está configurada la variable de entorno
DEFAULT_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Intenta obtener la URL desde las variables de Render, si no, usa la por defecto
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Crear motor de base de datos con SSL obligatorio para Supabase en Render
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
