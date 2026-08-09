from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# =====================================================
# CONFIGURATION BASE DE DONNÉES
# =====================================================

# Fichier SQLite local → sport_app.db créé automatiquement
DATABASE_URL = "sqlite:///./sport_app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # nécessaire pour SQLite
)

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
