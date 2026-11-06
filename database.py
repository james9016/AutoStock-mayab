import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Credenciales y subdominios estructurados limpiamente
DB_USER = "postgres.grnqhgctjjahvhkjckxa"
DB_PASS = "AutoStockMayab2026"
DB_HOST = "://supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

# URL base limpia. Agregamos parámetros explícitos para el pooling y SSL directo compatible con Render
DEFAULT_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

# Render inyecta automáticamente la variable DATABASE_URL en producción
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Asegurar compatibilidad de drivers si Render inyecta la URL vieja que inicia con 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Crear motor de base de datos optimizado para uso masivo simultáneo en bodega
engine = create_engine(
    DATABASE_URL, 
    pool_size=10,             # Mantiene conexiones persistentes listas para usar
    max_overflow=20,          # Capacidad extra para picos de tráfico en horas de alta venta
    pool_timeout=30,          # Tiempo máximo de espera antes de error por saturación
    pool_pre_ping=True        # Verifica la conexión antes de cada query para evitar caídas
)

# Sesión local inyectable en las rutas de FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarativa base para los modelos
Base = declarative_base()

def get_db():
    """Dependencia de FastAPI para control transaccional e inyección segura a base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
