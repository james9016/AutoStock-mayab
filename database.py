import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

servidor = os.getenv("DB_HOST", "aws-1-us-west-2" + ".pooler" + ".supabase" + ".com")

url_conexion = URL.create(
    drivername="postgresql",
    username=os.getenv("DB_USER", "postgres.grnqhgctjjahvhkjckxa"),
    password=os.getenv("DB_PASSWORD"),
    host=servidor,
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME", "postgres")
)

engine = create_engine(
    url_conexion,
    connect_args={"sslmode": "require"},
    pool_size=5,
    max_overflow=10,
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
        
