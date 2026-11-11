from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

servidor = "aws-0-us-east-1" + ".pooler" + ".supabase" + ".com"

url_conexion = URL.create(
    drivername="postgresql",
    username="postgres.grnqhgctjjahvhkjckxa",
    password="AutoStockMayab2026",
    host=servidor,
    port=5432,
    database="postgres"
)

engine = create_engine(
    url_conexion,
    connect_args={"sslmode": "require"},
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
