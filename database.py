from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# =====================================================
# CONFIGURATION BASE DE DONNÉES
# =====================================================



DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./sport_app.db"
)

# Render utilise postgres:// mais SQLAlchemy nécessite postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# Classe de base dont hériteront tous vos modèles
Base = declarative_base()

# Fabrique de sessions — utilisée dans chaque requête FastAPI
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# =====================================================
# DÉPENDANCE FastAPI (utilisée plus tard dans les routes)
# =====================================================

def get_db():
    """Ouvre une session DB et la ferme après chaque requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
