
# =============================================================================
# Règles de programmation
# =============================================================================

REPS=1
HOLD=2

Regles_par_mouv = {
    "Force": {
        REPS: {
            "min": 1,
            "max": 3
        },
        HOLD: {
            "min": 3,
            "max": 8
        }
    },

    "Moyen": {
        REPS: {
            "min": 3,
            "max": 6
        },
        HOLD: {
            "min": 6,
            "max": 12
        }
    },

    "Endurance": {
        REPS: {
            "min": 6,
            "max": 12
        },
        HOLD: {
            "min": 10,
            "max": 20
        }
    }
}

Regles_par_seance = {
    "Force": {
        REPS: {
            "min": 6,
            "max": 12
        },
        HOLD: {
            "min": 15,
            "max": 25
        }
    },

    "Moyen": {
        REPS: {
            "min": 12,
            "max": 25
        },
        HOLD: {
            "min": 25,
            "max": 40
        }
    },

    "Endurance": {
        REPS: {
            "min": 25,
            "max": 50
        },
        HOLD: {
            "min": 40,
            "max": 60
        }
    }
}

# =====================================================
# Definition du niveau actuel
# =====================================================

skills_table = {
    
    "FL press": {
        
        "type": REPS,

        "levels": {
            "elas -25": 14,
            "elas -15": 13,
            "elas -5": 12,
            "tuck": 11,
            "adv_tuck": 10,
            "one leg": 9,
            "straddle": 8,
            "full": 4
        }
    },
    
    "Planche press": {
        
        "type": REPS,

        "levels": {
            "elas -25": 8,
            "elas -15": 7,
            "elas -5": 6,
            "tuck": 6,
            "adv_tuck": 2,
            "one leg": 1,
            "straddle": 0,
            "full": 0
        }
    },
    
    "OAHS": {
        
        "type": HOLD,

        "levels": {
            "full": 0
        }
    },
    
    "HS": {
        
        "type": HOLD,

        "levels": {
            "full": 42
        }
    },
    
    "HSPU": {
        
        "type": REPS,

        "levels": {
            "elas -25": 17,
            "elas -15": 15,
            "elas -5": 12,
            "full": 9
        }
    },
    
    "90°push up": {
        
        "type": REPS,

        "levels": {
            "elas -25": 8,
            "elas -15": 4,
            "elas -5": 3,
            "straddle": 2,
            "full": 2
        }
    },
    
    "Planche push": {
        
        "type": REPS,

        "levels": {
            "elas -25": 15,
            "elas -15": 14,
            "elas -5": 13,
            "tuck": 12,
            "adv_tuck": 9,
            "one leg": 4,
            "straddle": 1,
            "full": 0
        }
    },
    
    "FL touch": {
        
        "type": HOLD,

        "levels": {
            "elas -25": 17,
            "elas -15": 15,
            "elas -5": 12,
            "adv_tuck": 5,
            "one leg": 4,
            "straddle": 3,
            "full": 1
        }
    },
    
    "FL pull up": {
        
        "type": REPS,

        "levels": {
            "elas -25": 17,
            "elas -15": 15,
            "elas -5": 12,
            "adv_tuck": 10,
            "one leg": 7,
            "straddle": 4,
            "full": 3
        }
    },

    "FL": {
        
        "type": HOLD,

        "levels": {
            "elas -25": 33,
            "elas -15": 32,
            "elas -5": 31,
            "tuck": 30,
            "adv_tuck": 25,
            "one leg": 20,
            "straddle": 15,
            "full": 12
        }
    },

    "Planche": {
        
        "type": HOLD,

        "levels": {
            "elas -25": 18,
            "elas -15": 17,
            "elas -5": 16,
            "tuck": 15,
            "adv_tuck": 14,
            "one leg": 10,
            "straddle": 4,
            "full": 0
        }
    }

}


