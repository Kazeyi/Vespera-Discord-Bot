# Constants for D&D System

# Years to skip between phases
# Phase 1 -> 2: 20-50 years
# Phase 2 -> 3: 500-1000 years
PHASE_TIME_SKIPS = {
    2: (20, 50),
    3: (500, 1000)
}

# Hex colors for different location themes
LOCATION_THEMES = {
    "tavern": 0xD35400,
    "dungeon": 0x2C3E50,
    "forest": 0x27AE60,
    "city": 0x95A5A6,
    "mountain": 0x7F8C8D,
    "sea": 0x2980B9,
    "void": 0x8E44AD,
    "unknown": 0x3498DB
}

# Environmental Mechanics
ZONE_TAGS = {
    "volcano": {
        "name": "Extreme Heat",
        "description": "DC 10 CON Save at end of turn or gain 1 level of exhaustion",
        "damage_type": "fire"
    },
    "ocean": {
        "name": "Deep Waters",
        "description": "DC 12 STR (Athletics) check to move. Drowning at 0 HP. Bludgeoning damage reduced by half.",
        "damage_type": "bludgeoning"
    },
    "forest": {
        "name": "Dense Vegetation",
        "description": "Visibility reduced to 30 feet. Ranged attacks at disadvantage beyond 60 feet.",
        "damage_type": "piercing"
    },
    "dungeon": {
        "name": "Darkness & Oppression",
        "description": "No natural light. Magical light sources cast shadows. Perception checks have disadvantage in darkness.",
        "damage_type": "necrotic"
    },
    "desert": {
        "name": "Scorching Dryness",
        "description": "DC 10 CON Save every hour or lose 1d4 HP from dehydration. Fire resistance gains +2.",
        "damage_type": "fire"
    }
}

# Path to audio files
AUDIO_PATH = "./audio/"

# Default API Model
FAST_MODEL = "llama-3.3-70b-versatile"
