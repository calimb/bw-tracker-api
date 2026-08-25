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

class GoalSessionInput(BaseModel):
    goal_id: int
    fatigue: int = None
    sleep_hours: float = None
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
    from core import analyze_session, adjust_prescription, check_goal_reached

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Objectif introuvable")

    # Création de la séance
    session = GoalSession(
        goal_id=goal_id,
        session_type="Standard",
        date=datetime.now(),
        fatigue=body.fatigue,
        sleep_hours=body.sleep_hours,
    )
    db.add(session)
    db.flush()

    analysis_by_movement = {}
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
                rir=r.rir
            ))

        # Analyser
        results_dicts = [
            {"reps_performed": r.reps_performed, "rir": r.rir}
            for r in set_results
        ]

        analysis = analyze_session(
            results=results_dicts,
            session_type=body.session_type,
            target_reps=movement.prescribed_reps,
            target_sets=movement.prescribed_sets
        )

        # Ajuster prescription
        adjustment = adjust_prescription(movement, analysis, db)

        analysis_by_movement[movement_id] = {
            "skill_name": movement.skill.name,
            "analysis": analysis,
            "next_prescription": adjustment
        }

        # Vérifier si objectif atteint
        if check_goal_reached(movement, results_dicts):
            goal_reached_movements.append(movement.skill.name)

    db.commit()

    return {
        "session_id": session.id,
        "analysis": analysis_by_movement,
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
    from models import GoalMovement, GoalSession, GoalSetResult
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
        db.commit()
        return {"message": "Migration réussie"}
    except Exception as e:
        return {"message": f"Erreur : {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
