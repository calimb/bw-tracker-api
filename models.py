from sqlalchemy import (
    Column, Integer, String, Float,
    Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# =====================================================
# CONSTANTES (remplacent data.py)
# =====================================================

REPS = "REPS"
HOLD = "HOLD"

# =====================================================
# MODÈLE : Skill
# Correspond à votre classe skill.py + data.py (skills_table)
# =====================================================

class Skill(Base):

    __tablename__ = "skills"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, unique=True, nullable=False)
    skill_type = Column(String, nullable=False)  # "REPS" ou "HOLD"

    # Relation vers les niveaux de ce skill
    levels = relationship(
        "SkillLevel",
        back_populates="skill",
        cascade="all, delete-orphan"
    )

    # Relation vers les exercices utilisant ce skill
    exercises = relationship(
        "Exercise",
        back_populates="skill"
    )

    def get_best_level(self, minimum_required: int):
        """
        Retourne le niveau le plus accessible
        dépassant le minimum requis.
        Reprend la logique de votre skill.py.
        """
        valid = [
            (lvl.variation, lvl.value)
            for lvl in self.levels
            if lvl.value >= minimum_required
        ]
        if not valid:
            return None, None
        return min(valid, key=lambda x: x[1])

    def update_record(self, variation: str, value: int, db):
        """
        Met à jour le record d'une variation si battu.
        Reprend la logique de votre tracking.py.
        """
        level = next(
            (l for l in self.levels if l.variation == variation),
            None
        )
        if level and value > level.value:
            level.value = value
            db.commit()
            return True
        return False


# =====================================================
# MODÈLE : SkillLevel
# Nouveau — remplace le dict "levels" dans skills_table
# =====================================================

class SkillLevel(Base):

    __tablename__ = "skill_levels"

    id         = Column(Integer, primary_key=True, index=True)
    skill_id   = Column(Integer, ForeignKey("skills.id"), nullable=False)
    variation  = Column(String, nullable=False)   # ex: "tuck", "full", "elas -25"
    value      = Column(Integer, nullable=False)  # reps ou secondes

    skill = relationship("Skill", back_populates="levels")


# =====================================================
# MODÈLE : ProgramRules
# Nouveau — remplace vos dicts Regles_par_mouv / Regles_par_seance
# =====================================================

class ProgramRules(Base):

    __tablename__ = "program_rules"

    id             = Column(Integer, primary_key=True, index=True)
    session_type   = Column(String, nullable=False)  # "Force", "Moyen", "Endurance"
    movement_type  = Column(String, nullable=False)  # "REPS" ou "HOLD"
    scope          = Column(String, nullable=False)  # "par_mouv" ou "par_seance"
    min_value      = Column(Integer, nullable=False)
    max_value      = Column(Integer, nullable=False)


# =====================================================
# MODÈLE : User
# Nouveau — profil utilisateur
# =====================================================

class User(Base):

    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    username     = Column(String, unique=True, nullable=False)
    objectif     = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    token        = Column(String, nullable=True)

    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    goals = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan"
    )
# =====================================================
# MODÈLE : Session
# Correspond à votre classe session.py
# =====================================================

class Session(Base):

    __tablename__ = "sessions"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    date         = Column(DateTime, default=datetime.now)
    session_type = Column(String, nullable=False)  # "Force", "Moyen", "Endurance"

    user      = relationship("User", back_populates="sessions")
    exercises = relationship(
        "Exercise",
        back_populates="session",
        cascade="all, delete-orphan"
    )


# =====================================================
# MODÈLE : Exercise
# Correspond à votre classe exercice.py
# =====================================================

class Exercise(Base):

    __tablename__ = "exercises"

    id           = Column(Integer, primary_key=True, index=True)
    session_id   = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    skill_id     = Column(Integer, ForeignKey("skills.id"), nullable=False)
    variation    = Column(String, nullable=False)
    sets         = Column(Integer, nullable=False)
    work_per_set = Column(Integer, nullable=False)  # reps ou secondes prévus

    session = relationship("Session", back_populates="exercises")
    skill   = relationship("Skill", back_populates="exercises")
    results = relationship(
        "WorkoutResult",
        back_populates="exercise",
        cascade="all, delete-orphan"
    )

    def best_score(self) -> int:
        """Meilleur score réalisé sur cet exercice."""
        if not self.results:
            return 0
        return max(r.value for r in self.results)


# =====================================================
# MODÈLE : WorkoutResult
# Nouveau — stocke les reps/secondes réelles par série
# Remplace la liste reps_per_set dans tracking.py
# =====================================================

class WorkoutResult(Base):

    __tablename__ = "workout_results"

    id          = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    set_number  = Column(Integer, nullable=False)  # numéro de la série (1, 2, 3…)
    value       = Column(Integer, nullable=False)  # reps ou secondes réalisées
    is_record   = Column(Boolean, default=False)   # PR battu sur cette série ?

    exercise = relationship("Exercise", back_populates="results")

# =====================================================
# MODÈLE : Goal
# Un objectif avec un ou plusieurs mouvements
# =====================================================

class Goal(Base):

    __tablename__ = "goals"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String, nullable=False)  # ex: "Objectif HSPU"
    status      = Column(String, default="active")  # active / archived / deleted
    created_at  = Column(DateTime, default=datetime.now)
    archived_at = Column(DateTime, nullable=True)

    user      = relationship("User", back_populates="goals")
    movements = relationship(
        "GoalMovement",
        back_populates="goal",
        cascade="all, delete-orphan"
    )
    sessions = relationship(
        "GoalSession",
        back_populates="goal",
        cascade="all, delete-orphan"
    )


# =====================================================
# MODÈLE : GoalMovement
# Un mouvement dans un objectif
# =====================================================

class GoalMovement(Base):

    __tablename__ = "goal_movements"

    id                   = Column(Integer, primary_key=True, index=True)
    goal_id              = Column(Integer, ForeignKey("goals.id"), nullable=False)
    skill_id             = Column(Integer, ForeignKey("skills.id"), nullable=False)
    goal_reps            = Column(Integer, nullable=False)   # objectif de reps/hold
    current_max_reps     = Column(Integer, nullable=False)   # max actuel estimé
    next_session_type    = Column(String, default="Force")   # Force ou Volume
    prescribed_reps      = Column(Integer, nullable=True)    # reps prescrites prochaine séance
    prescribed_sets      = Column(Integer, nullable=True)    # séries prescrites prochaine séance
    consecutive_appropriate = Column(Integer, default=0)     # nb séances APPROPRIATE consécutives
    last_session_date    = Column(DateTime, nullable=True)
    last_retest_date     = Column(DateTime, nullable=True)

    goal  = relationship("Goal", back_populates="movements")
    skill = relationship("Skill")


# =====================================================
# MODÈLE : GoalSession
# Une séance liée à un objectif
# =====================================================

class GoalSession(Base):

    __tablename__ = "goal_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    goal_id      = Column(Integer, ForeignKey("goals.id"), nullable=False)
    session_type = Column(String, nullable=False)   # Force ou Volume
    date         = Column(DateTime, default=datetime.now)
    status       = Column(String, default="completed")  # completed / abandoned

    goal     = relationship("Goal", back_populates="sessions")
    results  = relationship(
        "GoalSetResult",
        back_populates="session",
        cascade="all, delete-orphan"
    )


# =====================================================
# MODÈLE : GoalSetResult
# Résultat d'une série dans une séance
# =====================================================

class GoalSetResult(Base):

    __tablename__ = "goal_set_results"

    id              = Column(Integer, primary_key=True, index=True)
    session_id      = Column(Integer, ForeignKey("goal_sessions.id"), nullable=False)
    goal_movement_id = Column(Integer, ForeignKey("goal_movements.id"), nullable=False)
    set_number      = Column(Integer, nullable=False)
    reps_performed  = Column(Integer, nullable=False)
    rir             = Column(Integer, nullable=False)

    session      = relationship("GoalSession", back_populates="results")
    goal_movement = relationship("GoalMovement")
