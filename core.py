from sqlalchemy.orm import Session
from models import GoalMovement, GoalSetResult, GoalSession
from datetime import datetime

# =====================================================
# TABLE DE CORRESPONDANCE MAX → REPS
# Force et Volume
# =====================================================

REPS_TABLE = {
    3:  {"Force": 2,   "Volume": 1},
    4:  {"Force": 3,   "Volume": 2},
    5:  {"Force": 3,   "Volume": 2},
    6:  {"Force": 4,   "Volume": 3},
    7:  {"Force": 5,   "Volume": 3},
    8:  {"Force": 5,   "Volume": 4},
    9:  {"Force": 6,   "Volume": 4},
    10: {"Force": 6,   "Volume": 4},
    11: {"Force": 7,   "Volume": 5},
    12: {"Force": 7,   "Volume": 5},
}

TARGET_RIR = {
    "Force":  2,
    "Volume": 3,
}

MAX_SETS = 10
MIN_SETS = 3

# =====================================================
# RÉCUPÉRER REPS DEPUIS LA TABLE
# =====================================================

def get_table_reps(max_reps: int, session_type: str) -> int:
    """Retourne les reps prescrites depuis la table."""
    if max_reps in REPS_TABLE:
        return REPS_TABLE[max_reps][session_type]
    elif max_reps > 12:
        # Extrapolation au-delà de 12
        base = REPS_TABLE[12][session_type]
        extra = (max_reps - 12) // 2
        return base + extra
    else:
        return 1

# =====================================================
# GÉNÉRER PRESCRIPTION INITIALE
# =====================================================

def generate_prescription(
    current_max_reps: int,
    session_type: str,
    prescribed_reps: int = None,
    prescribed_sets: int = None
) -> dict:
    """
    Génère la prescription pour une séance.
    Si prescribed_reps/sets existent déjà, on les utilise.
    Sinon on part de la table.
    """
    if prescribed_reps is None:
        reps = get_table_reps(current_max_reps, session_type)
    else:
        reps = prescribed_reps

    if prescribed_sets is None:
        # Volume cible / reps par série
        if session_type == "Force":
            target_volume = current_max_reps * 3
        else:
            target_volume = current_max_reps * 4

        sets = max(MIN_SETS, round(target_volume / reps))
        sets = min(sets, MAX_SETS)
    else:
        sets = prescribed_sets

    return {
        "reps": reps,
        "sets": sets,
        "target_rir": TARGET_RIR[session_type],
        "session_type": session_type,
    }

# =====================================================
# ANALYSER UNE SÉANCE
# =====================================================

def analyze_session(
    results: list,
    session_type: str,
    target_reps: int,
    target_sets: int
) -> dict:
    """
    Analyse les résultats d'une séance.
    results = liste de dicts {reps_performed, rir}
    """
    if not results:
        return {"status": "NO_DATA"}

    target_rir = TARGET_RIR[session_type]
    total_reps = sum(r["reps_performed"] for r in results)
    target_volume = target_reps * target_sets
    completion_ratio = total_reps / target_volume if target_volume > 0 else 0
    average_rir = sum(r["rir"] for r in results) / len(results)
    last_set_rir = results[-1]["rir"]

    # Détermination du statut
    if average_rir >= target_rir + 1:
        status = "TOO_EASY"
    elif average_rir < target_rir - 1:
        status = "TOO_HARD"
    else:
        status = "APPROPRIATE"

    return {
        "status": status,
        "total_reps": total_reps,
        "target_volume": target_volume,
        "completion_ratio": round(completion_ratio, 2),
        "average_rir": round(average_rir, 2),
        "last_set_rir": last_set_rir,
        "target_rir": target_rir,
    }

# =====================================================
# AJUSTER LA PRESCRIPTION
# =====================================================

def adjust_prescription(
    movement: GoalMovement,
    analysis: dict,
    db: Session
) -> dict:
    """
    Ajuste la prescription pour la prochaine séance
    selon l'analyse de la séance actuelle.
    """
    session_type = movement.next_session_type
    current_reps = movement.prescribed_reps or get_table_reps(
        movement.current_max_reps, session_type
    )
    current_sets = movement.prescribed_sets or MIN_SETS
    status = analysis["status"]
    max_reps_table = get_table_reps(movement.current_max_reps, session_type)
    suggestion = None

    if status == "TOO_EASY":
        movement.consecutive_appropriate = 0
        if current_reps < max_reps_table:
            # Augmenter reps
            current_reps += 1
        elif current_sets < MAX_SETS:
            # Augmenter séries
            current_sets += 1
        else:
            # Max atteint → suggérer variation supérieure
            suggestion = "INCREASE_VARIATION"

    elif status == "TOO_HARD":
        movement.consecutive_appropriate = 0
        if current_reps > 1:
            # Diminuer reps
            current_reps -= 1
        elif current_sets > MIN_SETS:
            # Diminuer séries
            current_sets -= 1
        else:
            # Min atteint → suggérer variation inférieure
            suggestion = "DECREASE_VARIATION"

    elif status == "APPROPRIATE":
        movement.consecutive_appropriate += 1
        if movement.consecutive_appropriate >= 3:
            # Progression après 3 séances consécutives
            movement.consecutive_appropriate = 0
            if current_reps < max_reps_table:
                current_reps += 1
            elif current_sets < MAX_SETS:
                current_sets += 1

    # Alterner Force / Volume
    next_type = "Volume" if session_type == "Force" else "Force"

    # Mise à jour en base
    movement.prescribed_reps = current_reps
    movement.prescribed_sets = current_sets
    movement.next_session_type = next_type
    movement.last_session_date = datetime.now()
    db.commit()

    return {
        "next_session_type": next_type,
        "prescribed_reps": current_reps,
        "prescribed_sets": current_sets,
        "suggestion": suggestion,
    }

# =====================================================
# VÉRIFIER SI RETEST NÉCESSAIRE
# =====================================================

def needs_retest(movement: GoalMovement) -> bool:
    """Retourne True si le retest du max est recommandé (~14 jours)."""
    if movement.last_retest_date is None:
        return False
    days_since = (datetime.now() - movement.last_retest_date).days
    return days_since >= 14

# =====================================================
# VÉRIFIER SI OBJECTIF ATTEINT
# =====================================================

def check_goal_reached(
    movement: GoalMovement,
    results: list
) -> bool:
    """Retourne True si le goalReps a été atteint dans la séance."""
    if not results:
        return False
    max_reps = max(r["reps_performed"] for r in results)
    return max_reps >= movement.goal_reps