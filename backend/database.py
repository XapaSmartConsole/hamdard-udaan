from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# =====================================
# DATABASE CONFIG (USING ROOT)
# =====================================

DB_USER = "root"
DB_PASSWORD = "ayanq123"   # 👈 SAME AS MYSQL WORKBENCH
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "rspl_demo"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
