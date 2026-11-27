import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    url_conexion = DATABASE_URL
else:
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    if not all([db_user, db_pass, db_host]):
        raise RuntimeError("Faltan variables de entorno de base de datos (DATABASE_URL o DB_USER/DB_PASSWORD/DB_HOST)")

    url_conexion = URL.create(
        drivername="postgresql",
        username=db_user,
        password=db_pass,
        host=db_host,
        port=int(os.getenv("DB_PORT", 6543)),
        database=os.getenv("DB_NAME", "postgres")
    )

engine = create_engine(
    url_conexion,
    connect_args={"sslmode": "require"},
    pool_size=5,
    max_overflow=5,
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
