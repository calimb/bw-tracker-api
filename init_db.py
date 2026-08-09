"""
init_db.py — à lancer une seule fois pour créer les tables
et pré-remplir la base avec vos skills et règles existants.
"""

from database import engine, SessionLocal, Base
from models import Skill, SkillLevel, ProgramRules, REPS, HOLD

# =====================================================
# CRÉATION DES TABLES
# =====================================================

def create_tables():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées.")

# =====================================================
# DONNÉES INITIALES — vos skills de data.py
# =====================================================

SKILLS_DATA = [
    {
        "name": "FL press",
        "skill_type": REPS,
        "levels": {
            "elas -25": 14, "elas -15": 13, "elas -5": 12,
            "tuck": 11, "adv_tuck": 10, "one leg": 9,
            "straddle": 8, "full": 4
        }
    },
    {
        "name": "Planche press",
        "skill_type": REPS,
        "levels": {
            "elas -25": 8, "elas -15": 7, "elas -5": 6,
            "tuck": 6, "adv_tuck": 2, "one leg": 1,
            "straddle": 0, "full": 0
        }
    },
    {
        "name": "OAHS",
        "skill_type": HOLD,
        "levels": {"full": 0}
    },
    {
        "name": "HS",
        "skill_type": HOLD,
        "levels": {"full": 42}
    },
    {
        "name": "HSPU",
        "skill_type": REPS,
        "levels": {
            "elas -25": 17, "elas -15": 15,
            "elas -5": 12, "full": 9
        }
    },
    {
        "name": "90°push up",
        "skill_type": REPS,
        "levels": {
            "elas -25": 8, "elas -15": 4,
            "elas -5": 3, "straddle": 2, "full": 2
        }
    },
    {
        "name": "Planche push",
        "skill_type": REPS,
        "levels": {
            "elas -25": 15, "elas -15": 14, "elas -5": 13,
            "tuck": 12, "adv_tuck": 9, "one leg": 4,
            "straddle": 1, "full": 0
        }
    },
    {
        "name": "FL touch",
        "skill_type": HOLD,
        "levels": {
            "elas -25": 17, "elas -15": 15, "elas -5": 12,
            "adv_tuck": 5, "one leg": 4, "straddle": 3, "full": 1
        }
    },
    {
        "name": "FL pull up",
        "skill_type": REPS,
        "levels": {
            "elas -25": 17, "elas -15": 15, "elas -5": 12,
            "adv_tuck": 10, "one leg": 7, "straddle": 4, "full": 3
        }
    },
    {
        "name": "FL",
        "skill_type": HOLD,
        "levels": {
            "elas -25": 33, "elas -15": 32, "elas -5": 31,
            "tuck": 30, "adv_tuck": 25, "one leg": 20,
            "straddle": 15, "full": 12
        }
    },
    {
        "name": "Planche",
        "skill_type": HOLD,
        "levels": {
            "elas -25": 18, "elas -15": 17, "elas -5": 16,
            "tuck": 15, "adv_tuck": 14, "one leg": 10,
            "straddle": 4, "full": 0
        }
    },
]

# =====================================================
# DONNÉES INITIALES — vos règles de data.py
# =====================================================

RULES_DATA = [
    # --- par_mouv ---
    {"session_type": "Force",     "movement_type": REPS, "scope": "par_mouv",   "min_value": 1,  "max_value": 3},
    {"session_type": "Force",     "movement_type": HOLD, "scope": "par_mouv",   "min_value": 3,  "max_value": 8},
    {"session_type": "Moyen",     "movement_type": REPS, "scope": "par_mouv",   "min_value": 3,  "max_value": 6},
    {"session_type": "Moyen",     "movement_type": HOLD, "scope": "par_mouv",   "min_value": 6,  "max_value": 12},
    {"session_type": "Endurance", "movement_type": REPS, "scope": "par_mouv",   "min_value": 6,  "max_value": 12},
    {"session_type": "Endurance", "movement_type": HOLD, "scope": "par_mouv",   "min_value": 10, "max_value": 20},
    # --- par_seance ---
    {"session_type": "Force",     "movement_type": REPS, "scope": "par_seance", "min_value": 6,  "max_value": 12},
    {"session_type": "Force",     "movement_type": HOLD, "scope": "par_seance", "min_value": 15, "max_value": 25},
    {"session_type": "Moyen",     "movement_type": REPS, "scope": "par_seance", "min_value": 12, "max_value": 25},
    {"session_type": "Moyen",     "movement_type": HOLD, "scope": "par_seance", "min_value": 25, "max_value": 40},
    {"session_type": "Endurance", "movement_type": REPS, "scope": "par_seance", "min_value": 25, "max_value": 50},
    {"session_type": "Endurance", "movement_type": HOLD, "scope": "par_seance", "min_value": 40, "max_value": 60},
]

# =====================================================
# INSERTION EN BASE
# =====================================================

def seed_database():

    db = SessionLocal()

    # Évite les doublons si relancé
    if db.query(Skill).count() > 0:
        print("⚠️  Base déjà remplie, seed ignoré.")
        db.close()
        return

    for skill_data in SKILLS_DATA:
        skill = Skill(
            name=skill_data["name"],
            skill_type=skill_data["skill_type"]
        )
        db.add(skill)
        db.flush()  # récupère l'id avant commit

        for variation, value in skill_data["levels"].items():
            db.add(SkillLevel(
                skill_id=skill.id,
                variation=variation,
                value=value
            ))

    for rule in RULES_DATA:
        db.add(ProgramRules(**rule))

    db.commit()
    db.close()
    print("✅ Données initiales insérées.")


if __name__ == "__main__":
    create_tables()
    seed_database()
