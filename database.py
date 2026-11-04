import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Credenciales de Supabase
DB_USER = "postgres.grnqhgctjjahvhkjckxa"
DB_PASS = "Jacqui.1118649021"
DB_HOST = "://supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

# Construcción directa de la URL limpia sin pasar por variables de entorno conflictivas
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
