from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text

from database import get_db, engine, Base
from models import (
    Skill, SkillLevel,
    Session as WorkoutSession,
    Exercise, WorkoutResult,
    User, ProgramRules,
    REPS, HOLD
)


import hashlib
import secrets

# =====================================================
# INITIALISATION
# =====================================================

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sport App API")

# =====================================================
# SCHÉMAS PYDANTIC
# Ces classes définissent le format des données
# échangées entre l'API et Flutter (JSON)
# =====================================================

class SkillLevelSchema(BaseModel):
    variation: str
    value: int

    class Config:
        from_attributes = True

class SkillSchema(BaseModel):
    id: int
    name: str
    skill_type: str
    levels: List[SkillLevelSchema]

    class Config:
        from_attributes = True

class WorkoutResultSchema(BaseModel):
    set_number: int
    value: int
    is_record: bool = False

    class Config:
        from_attributes = True

class ExerciseSchema(BaseModel):
    id: int
    skill_id: int
    skill_name: str = ""
    variation: str
    sets: int
    work_per_set: int
    results: List[WorkoutResultSchema] = []

    class Config:
        from_attributes = True

class SessionSchema(BaseModel):
    id: int
    date: datetime
    session_type: str
    exercises: List[ExerciseSchema] = []

    class Config:
        from_attributes = True

# --- Schémas pour les requêtes entrantes (POST/PUT) ---

class NewSessionRequest(BaseModel):
    user_id: int
    session_type: str          # "Force", "Moyen", "Endurance"
    selected_skills: List[str] # noms des skills choisis

class ResultInput(BaseModel):
    set_number: int
    value: int

class ExerciseResultsInput(BaseModel):
    exercise_id: int
    results: List[ResultInput]

class UpdateLevelInput(BaseModel):
    value: int

# =====================================================
# ROUTES — SKILLS
# =====================================================

@app.get("/skills", response_model=List[SkillSchema])
def get_skills(db: Session = Depends(get_db)):
    """Retourne tous les skills avec leurs niveaux."""
    return db.query(Skill).all()


@app.get("/skills/{skill_id}", response_model=SkillSchema)
def get_skill(skill_id: int, db: Session = Depends(get_db)):
    """Retourne un skill précis par son id."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill introuvable")
    return skill


@app.put("/skills/{skill_id}/levels/{variation}")
def update_skill_level(
    skill_id: int,
    variation: str,
    body: UpdateLevelInput,
    db: Session = Depends(get_db)
):
    """Met à jour la valeur d'une variation (record manuel)."""
    level = db.query(SkillLevel).filter(
        SkillLevel.skill_id == skill_id,
        SkillLevel.variation == variation
    ).first()

    if not level:
        raise HTTPException(status_code=404, detail="Variation introuvable")

    level.value = body.value
    db.commit()
    return {"message": "Niveau mis à jour", "variation": variation, "value": body.value}

# =====================================================
# ROUTES — SÉANCES
# =====================================================

@app.get("/sessions", response_model=List[SessionSchema])
def get_sessions(db: Session = Depends(get_db)):
    """Retourne tout l'historique des séances."""
    sessions = db.query(WorkoutSession).order_by(
        WorkoutSession.date.desc()
    ).all()
    for session in sessions:
        for exercise in session.exercises:
            exercise.skill_name = exercise.skill.name
    return sessions

@app.get("/sessions/{session_id}", response_model=SessionSchema)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Retourne une séance précise par son id."""
    session = db.query(WorkoutSession).filter(
        WorkoutSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    return session

@app.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Supprime une séance et ses exercices."""
    session = db.query(WorkoutSession).filter(
        WorkoutSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    db.delete(session)
    db.commit()
    return {"message": "Séance supprimée"}

@app.delete("/sessions")
def clear_history(db: Session = Depends(get_db)):
    """Supprime tout l'historique."""
    db.query(WorkoutSession).delete()
    db.commit()
    return {"message": "Historique effacé"}

# =====================================================
# ROUTES — RÉSULTATS
# =====================================================

@app.post("/sessions/{session_id}/results")
def save_results(
    session_id: int,
    results: List[ExerciseResultsInput],
    db: Session = Depends(get_db)
):
    """
    Enregistre les résultats réels d'une séance.
    Met à jour les records si battus.
    """
    for exercise_input in results:

        exercise = db.query(Exercise).filter(
            Exercise.id == exercise_input.exercise_id
        ).first()

        if not exercise:
            continue

        for result in exercise_input.results:

            # Vérifie si c'est un record
            level = db.query(SkillLevel).filter(
                SkillLevel.skill_id == exercise.skill_id,
                SkillLevel.variation == exercise.variation
            ).first()

            is_record = False
            if level and result.value > level.value:
                level.value = result.value
                is_record = True

            db.add(WorkoutResult(
                exercise_id=exercise.id,
                set_number=result.set_number,
                value=result.value,
                is_record=is_record
            ))

    db.commit()
    return {"message": "Résultats enregistrés"}

# =====================================================
# ROUTES — UTILISATEURS
# =====================================================

@app.post("/users")
def create_user(username: str, db: Session = Depends(get_db)):
    """Crée un utilisateur."""
    existing = db.query(User).filter(
        User.username == username
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nom déjà utilisé")
    user = User(username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username}


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    """Retourne tous les utilisateurs."""
    return db.query(User).all()

# =====================================================
# AUTHENTIFICATION
# =====================================================

@app.post("/auth/register")
def register(username: str, password: str, db: Session = Depends(get_db)):
    """Crée un compte utilisateur."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nom déjà utilisé")
    
    # Hash du mot de passe
    hashed = hashlib.sha256(password.encode()).hexdigest()
    token = secrets.token_hex(32)
    
    user = User(
        username=username,
        password_hash=hashed,
        token=token
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "token": token}


@app.post("/auth/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    """Connexion utilisateur."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    hashed = hashlib.sha256(password.encode()).hexdigest()
    if user.password_hash != hashed:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    
    # Nouveau token à chaque connexion
    user.token = secrets.token_hex(32)
    db.commit()
    return {"id": user.id, "username": user.username, "token": user.token}


@app.get("/auth/me")
def get_me(token: str, db: Session = Depends(get_db)):
    """Vérifie le token et retourne l'utilisateur connecté."""
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Token invalide")
    return {"id": user.id, "username": user.username}

# =====================================================
# LANCEMENT
# =====================================================

@app.get("/skills/{skill_id}/progression")
def get_progression(skill_id: int, db: Session = Depends(get_db)):
    """
    Retourne l'évolution des records pour un skill
    au fil des séances d'objectifs.
    """
    from models import GoalMovement, GoalSetResult, GoalSession

    # Récupère tous les mouvements liés à ce skill
    movements = db.query(GoalMovement).filter(
        GoalMovement.skill_id == skill_id
    ).all()

    progression = []

    for movement in movements:
        # Récupère toutes les séances liées à ce mouvement
        results = db.query(GoalSetResult).filter(
            GoalSetResult.goal_movement_id == movement.id
        ).join(GoalSession).order_by(
            GoalSession.date.asc()
        ).all()

        # Groupe par séance
        from collections import defaultdict
        by_session = defaultdict(list)
        for r in results:
            by_session[r.session_id].append(r)

        for session_id, session_results in by_session.items():
            session = db.query(GoalSession).filter(
                GoalSession.id == session_id
            ).first()
            best = max(r.reps_performed for r in session_results)
            progression.append({
                "date": session.date.strftime("%d/%m/%Y"),
                "variation": session.session_type,
                "best": best
            })

    return progression

@app.get("/skills/{skill_id}/weekly")
def get_weekly(skill_id: int, db: Session = Depends(get_db)):
    """
    Retourne le total des reps/sec par semaine
    pour un skill donné.
    """
    from models import GoalMovement, GoalSetResult, GoalSession

    movements = db.query(GoalMovement).filter(
        GoalMovement.skill_id == skill_id
    ).all()

    weekly = {}

    for movement in movements:
        results = db.query(GoalSetResult).filter(
            GoalSetResult.goal_movement_id == movement.id
        ).join(GoalSession).order_by(
            GoalSession.date.asc()
        ).all()

        for r in results:
            session = db.query(GoalSession).filter(
                GoalSession.id == r.session_id
            ).first()
            date = session.date
            week_key = f"{date.year}-S{date.isocalendar()[1]:02d}"
            total = r.reps_performed
            key = f"{week_key}|{session.session_type}"

            if key not in weekly:
                weekly[key] = {
                    "week": week_key,
                    "variation": session.session_type,
                    "total": 0
                }
            weekly[key]["total"] += total

    return sorted(weekly.values(), key=lambda x: x["week"])

# =====================================================
# SCHÉMAS — OBJECTIFS
# =====================================================

class GoalMovementInput(BaseModel):
    skill_id: int = None
    skill_name: str = None      # si nouveau mouvement
    skill_type: str = None      # REPS ou HOLD si nouveau
    goal_reps: int
    current_max_reps: int = None  # optionnel si déjà dans niveaux

class CreateGoalInput(BaseModel):
    user_id: int
    name: str
    movements: List[GoalMovementInput]

class SetResultInput(BaseModel):
    goal_movement_id: int
    set_number: int
    reps_performed: int
    rir: int
    duration_seconds: int = None

class GoalSessionInput(BaseModel):
    goal_id: int
    fatigue: int = None
    sleep_hours: float = None
    session_date: str = None
    results: List[SetResultInput]

class RetestInput(BaseModel):
    new_max_reps: int

# =====================================================
# ROUTES — OBJECTIFS
# =====================================================

@app.post("/goals")
def create_goal(body: CreateGoalInput, db: Session = Depends(get_db)):
    """Crée un nouvel objectif avec ses mouvements."""

    from models import Goal, GoalMovement
    from core import get_table_reps, generate_prescription

    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    goal = Goal(
        user_id=body.user_id,
        name=body.name,
        status="active"
    )
    db.add(goal)
    db.flush()

    for m in body.movements:

        # Créer le skill si nouveau
        if m.skill_id is None:
            if not m.skill_name or not m.skill_type:
                raise HTTPException(
                    status_code=400,
                    detail="skill_name et skill_type requis pour un nouveau mouvement"
                )
            existing = db.query(Skill).filter(
                Skill.name == m.skill_name
            ).first()
            if existing:
                skill = existing
            else:
                skill = Skill(name=m.skill_name, skill_type=m.skill_type)
                db.add(skill)
                db.flush()
        else:
            skill = db.query(Skill).filter(Skill.id == m.skill_id).first()
            if not skill:
                raise HTTPException(status_code=404, detail="Skill introuvable")

        # Récupérer currentMaxReps depuis les niveaux si non fourni
        current_max = m.current_max_reps
        if current_max is None:
            best_level = max(
                (l.value for l in skill.levels),
                default=1
            )
            current_max = best_level

        # Prescription initiale
        prescription = generate_prescription(current_max, "Force")

        goal_movement = GoalMovement(
            goal_id=goal.id,
            skill_id=skill.id,
            goal_reps=m.goal_reps,
            current_max_reps=current_max,
            next_session_type="Force",
            prescribed_reps=prescription["reps"],
            prescribed_sets=prescription["sets"],
            last_retest_date=datetime.now()
        )
        db.add(goal_movement)

    db.commit()
    db.refresh(goal)
    return {"id": goal.id, "name": goal.name, "status": goal.status}


@app.get("/goals")
def get_goals(user_id: int, db: Session = Depends(get_db)):
    """Retourne les objectifs actifs d'un utilisateur."""
    from models import Goal, GoalMovement

    goals = db.query(Goal).filter(
        Goal.user_id == user_id,
        Goal.status == "active"
    ).all()

    result = []
    for goal in goals:
        movements = []
        for m in goal.movements:
            days_since = None
            if m.last_session_date:
                days_since = (datetime.now() - m.last_session_date).days

            movements.append({
                "id": m.id,
                "skill_id": m.skill_id,
                "skill_name": m.skill.name,
                "goal_reps": m.goal_reps,
                "current_max_reps": m.current_max_reps,
                "next_session_type": m.next_session_type,
                "prescribed_reps": m.prescribed_reps,
                "prescribed_sets": m.prescribed_sets,
                "days_since_last_session": days_since,
                "needs_retest": (
                    datetime.now() - m.last_retest_date
                ).days >= 14 if m.last_retest_date else False
            })

        result.append({
            "id": goal.id,
            "name": goal.name,
            "status": goal.status,
            "created_at": goal.created_at,
            "movements": movements
        })

    return result


@app.post("/goals/{goal_id}/session")
def start_goal_session(
    goal_id: int,
    body: GoalSessionInput,
    db: Session = Depends(get_db)
):
    """Enregistre une séance et analyse les résultats."""
    from models import Goal, GoalMovement, GoalSession, GoalSetResult
    from core import check_goal_reached

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Objectif introuvable")

    # Création de la séance
    session = GoalSession(
        goal_id=goal_id,
        session_type="Standard",
        date=datetime.fromisoformat(body.session_date) if body.session_date else datetime.now(),
        fatigue=body.fatigue,
        sleep_hours=body.sleep_hours,
    )
    db.add(session)
    db.flush()

    goal_reached_movements = []

    # Grouper résultats par mouvement
    from collections import defaultdict
    results_by_movement = defaultdict(list)
    for r in body.results:
        results_by_movement[r.goal_movement_id].append(r)

    for movement_id, set_results in results_by_movement.items():

        movement = db.query(GoalMovement).filter(
            GoalMovement.id == movement_id
        ).first()

        if not movement:
            continue

        # Sauvegarder les séries
        for r in set_results:
            db.add(GoalSetResult(
                session_id=session.id,
                goal_movement_id=movement_id,
                set_number=r.set_number,
                reps_performed=r.reps_performed,
                rir=r.rir,
                duration_seconds=r.duration_seconds if hasattr(r, 'duration_seconds') else None
            ))

        # Mettre à jour le max si record battu
        best = max(r.reps_performed for r in set_results)
        if best > movement.current_max_reps:
            movement.current_max_reps = best

        # Vérifier si objectif atteint
        results_dicts = [
            {"reps_performed": r.reps_performed, "rir": r.rir}
            for r in set_results
        ]

        if check_goal_reached(movement, results_dicts):
            goal_reached_movements.append(movement.skill.name)

        movement.last_session_date = datetime.now()
        db.commit()

    db.commit()

    return {
        "session_id": session.id,
        "analysis": {},
        "goal_reached": goal_reached_movements
    }

@app.patch("/goals/{goal_id}/status")
def update_goal_status(
    goal_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Archive ou supprime un objectif."""
    from models import Goal

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Objectif introuvable")

    if status not in ["active", "archived", "deleted"]:
        raise HTTPException(status_code=400, detail="Statut invalide")

    goal.status = status
    if status == "archived":
        goal.archived_at = datetime.now()

    db.commit()
    return {"message": f"Objectif {status}"}


@app.patch("/goals/{goal_id}/movements/{movement_id}/retest")
def retest_max(
    goal_id: int,
    movement_id: int,
    body: RetestInput,
    db: Session = Depends(get_db)
):
    """Met à jour le max après retest et recalcule la prescription."""
    from models import GoalMovement
    from core import generate_prescription

    movement = db.query(GoalMovement).filter(
        GoalMovement.id == movement_id,
        GoalMovement.goal_id == goal_id
    ).first()

    if not movement:
        raise HTTPException(status_code=404, detail="Mouvement introuvable")

    movement.current_max_reps = body.new_max_reps
    movement.last_retest_date = datetime.now()
    movement.consecutive_appropriate = 0

    prescription = generate_prescription(
        body.new_max_reps,
        movement.next_session_type
    )
    movement.prescribed_reps = prescription["reps"]
    movement.prescribed_sets = prescription["sets"]

    db.commit()
    return {
        "message": "Max mis à jour",
        "new_prescription": prescription
    }

@app.get("/calendar/{user_id}")
def get_calendar(user_id: int, db: Session = Depends(get_db)):
    """Retourne toutes les séances pour le calendrier."""
    from models import Goal, GoalSession, GoalSetResult

    # Récupère tous les objectifs de l'utilisateur
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()

    result = []
    for goal in goals:
        for session in goal.sessions:
            exercises = []
            # Groupe les résultats par mouvement
            from collections import defaultdict
            by_movement = defaultdict(list)
            for r in session.results:
                by_movement[r.goal_movement_id].append(r)

            for movement_id, results in by_movement.items():
                movement = next(
                    m for m in goal.movements
                    if m.id == movement_id
                )
                exercises.append({
                    "skill_name": movement.skill.name,
                    "variation": "",
                    "results": [
                        {
                            "set_number": r.set_number,
                            "value": r.reps_performed,
                            "is_record": False
                        }
                        for r in results
                    ]
                })

            result.append({
                "id": session.id,
                "date": session.date.isoformat(),
                "session_type": session.session_type,
                "goal_id": goal.id,
                "exercises": exercises
            })

    return result

@app.post("/admin/init")
def init_database(db: Session = Depends(get_db)):
    """Initialise les tables et données de base."""
    from init_db import seed_database
    Base.metadata.create_all(bind=engine)
    seed_database()
    return {"message": "Base initialisée"}

@app.delete("/skills/{skill_id}/progression")
def delete_progression(skill_id: int, db: Session = Depends(get_db)):
    """Supprime toute la progression d'un skill."""
    from models import GoalMovement, GoalSetResult

    movements = db.query(GoalMovement).filter(
        GoalMovement.skill_id == skill_id
    ).all()

    for movement in movements:
        db.query(GoalSetResult).filter(
            GoalSetResult.goal_movement_id == movement.id
        ).delete()

    db.commit()
    return {"message": "Progression supprimée"}

# =====================================================
# ROUTES — ANALYSE ET GRAPHES
# =====================================================

@app.get("/goals/{goal_id}/movements/{movement_id}/analytics")
def get_analytics(
    goal_id: int,
    movement_id: int,
    db: Session = Depends(get_db)
):
    """Retourne tous les capteurs et données pour les graphes."""
    from models import Goal, GoalMovement, GoalSession, GoalSetResult
    from collections import defaultdict

    movement = db.query(GoalMovement).filter(
        GoalMovement.id == movement_id,
        GoalMovement.goal_id == goal_id
    ).first()

    if not movement:
        raise HTTPException(status_code=404, detail="Mouvement introuvable")

    goal = db.query(Goal).filter(Goal.id == goal_id).first()

    # Récupère toutes les séances de l'objectif triées par date
    sessions = db.query(GoalSession).filter(
        GoalSession.goal_id == goal_id
    ).order_by(GoalSession.date.asc()).all()

    # Date de la première séance (pour calcul semaine personnalisée)
    first_session_date = sessions[0].date if sessions else None

    sessions_data = []
    weekly_data = defaultdict(lambda: {
        "total_reps": 0,
        "max_reps": 0,
        "all_rir": [],
    })

    prev_date = None

    for session in sessions:
        # Résultats de ce mouvement dans cette séance
        results = db.query(GoalSetResult).filter(
            GoalSetResult.session_id == session.id,
            GoalSetResult.goal_movement_id == movement_id
        ).order_by(GoalSetResult.set_number.asc()).all()

        if not results:
            continue

        # Calcul semaine personnalisée
        if first_session_date:
            days_from_start = (session.date - first_session_date).days
            # Lundi comme début de semaine
            first_weekday = first_session_date.weekday()
            adjusted_days = days_from_start + first_weekday
            custom_week = (adjusted_days // 7) + 1
        else:
            custom_week = 1

        # Capteurs
        reps_list = [r.reps_performed for r in results]
        rir_list = [r.rir for r in results]
        durations = [r.duration_seconds for r in results if r.duration_seconds]

        max_reps = max(reps_list)
        total_reps = sum(reps_list)
        avg_reps = round(total_reps / len(reps_list), 1)
        avg_rir = round(sum(rir_list) / len(rir_list), 1)
        first_reps = reps_list[0]
        last_reps = reps_list[-1]
        first_rir = rir_list[0]
        last_rir = rir_list[-1]
        nb_sets = len(results)
        diff_first_last = first_reps - last_reps
        avg_rest = round(sum(durations) / len(durations), 1) if durations else None

        # Jours de repos
        rest_days = (session.date - prev_date).days - 1 if prev_date else 0
        prev_date = session.date

        # Données hebdomadaires
        week_key = f"S{custom_week}"
        weekly_data[week_key]["total_reps"] += total_reps
        weekly_data[week_key]["max_reps"] = max(
            weekly_data[week_key]["max_reps"], max_reps
        )
        weekly_data[week_key]["all_rir"].extend(rir_list)

        sessions_data.append({
            "date": session.date.strftime("%d/%m/%Y"),
            "week": custom_week,
            "session_type": session.session_type,
            # Capteurs
            "rest_days": rest_days,
            "max_reps": max_reps,
            "total_reps": total_reps,
            "avg_rir": avg_rir,
            "first_reps": first_reps,
            "last_reps": last_reps,
            "avg_reps": avg_reps,
            "first_rir": first_rir,
            "last_rir": last_rir,
            "nb_sets": nb_sets,
            "diff_first_last": diff_first_last,
            "avg_rest_seconds": avg_rest,
            "fatigue": session.fatigue,
            "sleep_hours": session.sleep_hours,
        })

    # Données hebdomadaires finales
    weekly = []
    for week_key, data in sorted(weekly_data.items()):
        avg_rir_hebdo = round(
            sum(data["all_rir"]) / len(data["all_rir"]), 1
        ) if data["all_rir"] else 0
        efficacite = round(
            (data["max_reps"] / avg_rir_hebdo) * 100, 1
        ) if avg_rir_hebdo > 0 else 0
        weekly.append({
            "week": week_key,
            "total_reps": data["total_reps"],
            "max_reps": data["max_reps"],
            "avg_rir": avg_rir_hebdo,
            "efficacite": efficacite,
        })

    return {
        "skill_name": movement.skill.name,
        "goal_reps": movement.goal_reps,
        "sessions": sessions_data,
        "weekly": weekly,
    }

@app.post("/admin/migrate")
def migrate_database(db: Session = Depends(get_db)):
    """Ajoute les nouvelles colonnes si elles n'existent pas."""
    try:
        db.execute(text("ALTER TABLE goal_sessions ADD COLUMN IF NOT EXISTS fatigue INTEGER"))
        db.execute(text("ALTER TABLE goal_sessions ADD COLUMN IF NOT EXISTS sleep_hours FLOAT"))
        db.execute(text("ALTER TABLE goal_sessions ADD COLUMN IF NOT EXISTS rest_days INTEGER"))
        db.execute(text("ALTER TABLE goal_set_results ADD COLUMN IF NOT EXISTS duration_seconds INTEGER"))
        db.execute(text("ALTER TABLE goal_sessions ADD COLUMN IF NOT EXISTS max_at_session JSONB"))
        db.commit()
        return {"message": "Migration réussie"}
    except Exception as e:
        return {"message": f"Erreur : {str(e)}"}

@app.delete("/goal_sessions/{session_id}")
def delete_goal_session(session_id: int, db: Session = Depends(get_db)):
    """Supprime une séance d'objectif."""
    from models import GoalSession
    session = db.query(GoalSession).filter(
        GoalSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    db.delete(session)
    db.commit()
    return {"message": "Séance supprimée"}

@app.delete("/skills/unused")
def delete_unused_skills(db: Session = Depends(get_db)):
    """Supprime tous les skills non liés à un objectif."""
    from models import GoalMovement
    used_skill_ids = [
        m.skill_id for m in db.query(GoalMovement).all()
    ]
    skills_to_delete = db.query(Skill).filter(
        ~Skill.id.in_(used_skill_ids)
    ).all()
    for skill in skills_to_delete:
        db.delete(skill)
    db.commit()
    return {"message": f"{len(skills_to_delete)} skills supprimés"}

@app.get("/users/{user_id}/levels")
def get_user_levels(user_id: int, db: Session = Depends(get_db)):
    """Retourne les niveaux actuels de l'utilisateur depuis ses objectifs."""
    from models import Goal, GoalMovement

    goals = db.query(Goal).filter(
        Goal.user_id == user_id
    ).all()

    levels = {}
    for goal in goals:
        for movement in goal.movements:
            skill_id = movement.skill_id
            if skill_id not in levels:
                levels[skill_id] = {
                    "skill_id": skill_id,  # ajoutez cette ligne
                    "skill_name": movement.skill.name,
                    "skill_type": movement.skill.skill_type,
                    "current_max_reps": movement.current_max_reps,
                }
            else:
                # Garder le max le plus élevé si même skill dans plusieurs objectifs
                if movement.current_max_reps > levels[skill_id]["current_max_reps"]:
                    levels[skill_id]["current_max_reps"] = movement.current_max_reps

    return list(levels.values())

# =====================================================
# ROUTES — ADMIN
# =====================================================

ADMIN_USER_ID = 1  # votre user_id

@app.get("/admin/users")
def admin_get_users(user_id: int, db: Session = Depends(get_db)):
    """Liste tous les utilisateurs — accès admin uniquement."""
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username} for u in users]


@app.get("/admin/users/{target_user_id}/goals")
def admin_get_user_goals(
    target_user_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Retourne les objectifs d'un utilisateur — accès admin uniquement."""
    from models import Goal, GoalMovement
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")

    goals = db.query(Goal).filter(
        Goal.user_id == target_user_id,
        Goal.status != "deleted"
    ).all()

    result = []
    for goal in goals:
        movements = []
        for m in goal.movements:
            movements.append({
                "id": m.id,
                "skill_id": m.skill_id,
                "skill_name": m.skill.name,
                "goal_reps": m.goal_reps,
                "current_max_reps": m.current_max_reps,
                "next_session_type": m.next_session_type,
                "prescribed_reps": m.prescribed_reps,
                "prescribed_sets": m.prescribed_sets,
                "days_since_last_session": (
                    datetime.now() - m.last_session_date
                ).days if m.last_session_date else None,
            })
        result.append({
            "id": goal.id,
            "name": goal.name,
            "status": goal.status,
            "created_at": goal.created_at,
            "movements": movements,
        })

    return result


@app.get("/admin/users/{target_user_id}/levels")
def admin_get_user_levels(
    target_user_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Retourne les niveaux d'un utilisateur — accès admin uniquement."""
    from models import Goal, GoalMovement
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")

    goals = db.query(Goal).filter(
        Goal.user_id == target_user_id
    ).all()

    levels = {}
    for goal in goals:
        for movement in goal.movements:
            skill_id = movement.skill_id
            if skill_id not in levels:
                levels[skill_id] = {
                    "skill_id": skill_id,  # ajoutez cette ligne
                    "skill_name": movement.skill.name,
                    "skill_type": movement.skill.skill_type,
                    "current_max_reps": movement.current_max_reps,
                }
            else:
                if movement.current_max_reps > levels[skill_id]["current_max_reps"]:
                    levels[skill_id]["current_max_reps"] = movement.current_max_reps

    return list(levels.values())

# =====================================================
# SCHÉMAS — FAQ
# =====================================================

class FAQCreate(BaseModel):
    user_id: int
    category: str
    faq_type: str  # "app" ou "sport"
    question: str

class FAQAnswer(BaseModel):
    answer: str
    publish: bool = True

# =====================================================
# ROUTES — FAQ
# =====================================================

@app.get("/faqs")
def get_published_faqs(db: Session = Depends(get_db)):
    """Retourne toutes les FAQs publiées classées par thématique."""
    from models import FAQ
    faqs = db.query(FAQ).filter(
        FAQ.status == "published"
    ).order_by(FAQ.category, FAQ.votes.desc()).all()

    result = {}
    for faq in faqs:
        if faq.category not in result:
            result[faq.category] = []
        result[faq.category].append({
            "id": faq.id,
            "question": faq.question,
            "answer": faq.answer,
            "faq_type": faq.faq_type,
            "votes": faq.votes,
            "category": faq.category,
        })
    return result


@app.post("/faqs")
def create_faq(body: FAQCreate, db: Session = Depends(get_db)):
    """Soumet une nouvelle question."""
    from models import FAQ
    faq = FAQ(
        user_id=body.user_id,
        category=body.category,
        faq_type=body.faq_type,
        question=body.question,
        status="pending"
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return {"message": "Question soumise", "id": faq.id}


@app.post("/faqs/{faq_id}/vote")
def vote_faq(faq_id: int, user_id: int, db: Session = Depends(get_db)):
    """Vote pour une FAQ — un vote par utilisateur."""
    from models import FAQ, FAQVote
    existing = db.query(FAQVote).filter(
        FAQVote.faq_id == faq_id,
        FAQVote.user_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Déjà voté")
    db.add(FAQVote(faq_id=faq_id, user_id=user_id))
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if faq:
        faq.votes += 1
    db.commit()
    return {"message": "Vote enregistré"}


# =====================================================
# ROUTES — ADMIN FAQ
# =====================================================

@app.get("/admin/faqs")
def admin_get_faqs(user_id: int, db: Session = Depends(get_db)):
    """Retourne toutes les FAQs en attente — admin uniquement."""
    from models import FAQ
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")
    faqs = db.query(FAQ).order_by(
        FAQ.status, FAQ.votes.desc()
    ).all()
    return [
        {
            "id": f.id,
            "category": f.category,
            "faq_type": f.faq_type,
            "question": f.question,
            "answer": f.answer,
            "status": f.status,
            "votes": f.votes,
            "username": f.user.username,
            "created_at": f.created_at,
        }
        for f in faqs
    ]


@app.patch("/admin/faqs/{faq_id}")
def admin_answer_faq(
    faq_id: int,
    user_id: int,
    body: FAQAnswer,
    db: Session = Depends(get_db)
):
    """Répond à une FAQ et la publie — admin uniquement."""
    from models import FAQ
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ introuvable")
    faq.answer = body.answer
    if body.publish:
        faq.status = "published"
        faq.published_at = datetime.now()
    db.commit()
    return {"message": "FAQ mise à jour"}


@app.delete("/admin/faqs/{faq_id}")
def admin_delete_faq(
    faq_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Supprime une FAQ — admin uniquement."""
    from models import FAQ
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Accès refusé")
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ introuvable")
    db.delete(faq)
    db.commit()
    return {"message": "FAQ supprimée"}

@app.patch("/users/{user_id}/levels/{skill_id}")
def update_user_level(
    user_id: int,
    skill_id: int,
    value: int,
    db: Session = Depends(get_db)
):
    """Met à jour manuellement le max d'un mouvement."""
    from models import Goal, GoalMovement
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    updated = False
    for goal in goals:
        for movement in goal.movements:
            if movement.skill_id == skill_id:
                movement.current_max_reps = value
                updated = True
    if not updated:
        raise HTTPException(status_code=404, detail="Mouvement introuvable")
    db.commit()
    return {"message": "Niveau mis à jour", "value": value}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
