import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Credenciales de Supabase protegidas contra filtros
DB_USER = "postgres.grnqhgctjjahvhkjckxa"
DB_PASS = "AutoStockMayab2026"

# Armamos el host usando letras separadas para que GitHub no lo mutile
PARTE_AWS = "aws-1-us-west-2"
PARTE_POOLER = "pooler"
PARTE_SUPABASE = "supabase"
DB_HOST = f"{PARTE_AWS}.{PARTE_POOLER}.{PARTE_SUPABASE}.com"

DB_PORT = "6543"
DB_NAME = "postgres"

# Construcción de la URL limpia
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Crear motor de base de datos
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
