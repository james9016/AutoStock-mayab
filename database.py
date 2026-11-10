import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def obtener_url_segura():
    # 💡 REGLA DE SUPABASE PARA IPv4: Para enrutar el tenant sin depender de SNI,
    # el formato correcto en el puerto 6543 es 'usuario.id_proyecto'
    id_proyecto = "grnqhgctjjahvhkjckxa"
    u = f"postgres.{id_proyecto}"  
    p = "AutoStockMayab2026"
    
    # Balanceador global regionalizado (AWS us-east-1)
    h1 = "aws-0-us-east-1"
    h2 = "pooler"
    h3 = "supabase"
    h4 = "com"
    host_completo = f"{h1}.{h2}.{h3}.{h4}"
    
    # Puerto del Pooler Transaccional obligatorio para mapeo de usuarios compuestos
    puerto = "6543" 
    base_datos = "postgres"
    
    return f"postgresql://{u}:{p}@{host_completo}:{puerto}/{base_datos}"

DATABASE_URL = obtener_url_segura()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        # ✅ CRUCIAL PARA EL MODO TRANSACCIONAL: Desactiva por completo los prepared statements.
        # Esto permite que SQLAlchemy ejecute 'create_all()' y 'seed_database()' sobre el pooler
        # sin provocar desajustes de caché ni errores FATAL en el servidor de Supabase.
        "prepare_threshold": None
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
