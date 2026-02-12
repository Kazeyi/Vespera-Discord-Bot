# --- START OF FILE database.py ---
import sqlite3
import os
import time
import json
import random
from typing import Dict, List, Tuple, Optional, Any
from discord.ext import commands

DB_FILE = os.path.abspath("bot_database.db")

# --- CACHE SYSTEM ---
_cache = {}
CACHE_TTL = 60
MAX_CACHE_SIZE = 100

def get_cached(key: str) -> Optional[Any]:
    """Get item from cache if not expired"""
    if key in _cache:
        item = _cache[key]
        if time.time() - item['time'] < CACHE_TTL:
            return item['data']
        else:
            del _cache[key]
    return None

def set_cache(key: str, value: Any) -> None:
    """Set item in cache with TTL"""
    if len(_cache) >= MAX_CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[key] = {'data': value, 'time': time.time()}

def clear_cache(key: str) -> None:
    """Remove item from cache"""
    if key in _cache:
        del _cache[key]

def clear_all_cache() -> None:
    """Clear entire cache"""
    _cache.clear()

# --- DATABASE SCHEMA DEFINITION ---
SCHEMA = {
    # Core user tables
    "user_settings": """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            language TEXT DEFAULT 'English',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    "user_styles": """
        CREATE TABLE IF NOT EXISTS user_styles (
            user_id TEXT PRIMARY KEY,
            style TEXT DEFAULT 'Slang/Chat',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Moderation tables
    "mod_settings": """
        CREATE TABLE IF NOT EXISTS mod_settings (
            guild_id TEXT PRIMARY KEY,
            log_channel_id TEXT,
            mod_role_id TEXT,
            politics_channel_id TEXT,
            nsfw_channel_id TEXT,
            gaming_channel_id TEXT,
            vip_role_id TEXT,
            server_context TEXT DEFAULT 'General Gaming',
            ai_model TEXT DEFAULT 'models/gemma-3-27b-it',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    "user_reputation": """
        CREATE TABLE IF NOT EXISTS user_reputation (
            user_id TEXT,
            guild_id TEXT,
            toxicity_score INTEGER DEFAULT 0,
            last_offense_time REAL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (user_id, guild_id),
            FOREIGN KEY (guild_id) REFERENCES mod_settings(guild_id) ON DELETE CASCADE
        )
    """,
    
    # D&D Core tables
    "dnd_config": """
        CREATE TABLE IF NOT EXISTS dnd_config (
            guild_id TEXT PRIMARY KEY,
            parent_channel_id TEXT,
            current_location TEXT DEFAULT 'tavern',
            campaign_summary TEXT DEFAULT 'New Campaign Started.',
            party_stats TEXT,
            dnd_role_id TEXT,
            rulebook TEXT DEFAULT '5e 2024',
            active_party TEXT DEFAULT '[]',
            campaign_phase INTEGER DEFAULT 1,
            legends TEXT DEFAULT '[]',
            game_mode TEXT DEFAULT 'Narrative',
            quest_data TEXT,
            session_mode TEXT DEFAULT 'Architect',
            current_tone TEXT DEFAULT 'Standard',
            total_years_elapsed INTEGER DEFAULT 0,
            world_unique_point TEXT DEFAULT 'uninitialized',
            generation INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    "dnd_lore": """
        CREATE TABLE IF NOT EXISTS dnd_lore (
            guild_id TEXT,
            topic TEXT,
            description TEXT,
            timestamp REAL DEFAULT (strftime('%s', 'now')),
            created_at REAL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (guild_id, topic),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """,
    
    "dnd_history": """
        CREATE TABLE IF NOT EXISTS dnd_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL DEFAULT (strftime('%s', 'now')),
            metadata TEXT DEFAULT '{}'
        )
    """,
    
    "dnd_characters": """
        CREATE TABLE IF NOT EXISTS dnd_characters (
            user_id TEXT,
            guild_id TEXT,
            char_data TEXT,
            destiny_roll INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (user_id, guild_id),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """,
    
    "dnd_combat": """
        CREATE TABLE IF NOT EXISTS dnd_combat (
            thread_id TEXT,
            user_id TEXT,
            name TEXT,
            init_score INTEGER DEFAULT 0,
            current_hp INTEGER DEFAULT 0,
            max_hp INTEGER DEFAULT 0,
            is_monster INTEGER DEFAULT 0,
            conditions TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (thread_id, user_id)
        )
    """,
    
    # Rulebook system for D&D
    "dnd_rulebook": """
        CREATE TABLE IF NOT EXISTS dnd_rulebook (
            keyword TEXT PRIMARY KEY,
            rule_text TEXT,
            rule_type TEXT DEFAULT 'custom',
            source TEXT DEFAULT 'DM',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Audio/Media preferences
    "user_audio_prefs": """
        CREATE TABLE IF NOT EXISTS user_audio_prefs (
            user_id TEXT,
            guild_id TEXT,
            volume INTEGER DEFAULT 100,
            theme_music TEXT,
            sound_effects INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (user_id, guild_id)
        )
    """,
    
    # Command usage tracking
    "command_usage": """
        CREATE TABLE IF NOT EXISTS command_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            guild_id TEXT,
            command TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            timestamp REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Session tracking
    "session_tracking": """
        CREATE TABLE IF NOT EXISTS session_tracking (
            session_id TEXT PRIMARY KEY,
            guild_id TEXT,
            thread_id TEXT,
            start_time REAL DEFAULT (strftime('%s', 'now')),
            end_time REAL,
            duration INTEGER,
            player_count INTEGER DEFAULT 0,
            actions_count INTEGER DEFAULT 0,
            summary TEXT
        )
    """,
    
    # SRD 2024 Spells Library
    "srd_spells": """
        CREATE TABLE IF NOT EXISTS srd_spells (
            spell_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER DEFAULT 0,
            school TEXT,
            classes TEXT,
            casting_time TEXT,
            range TEXT,
            components TEXT,
            duration TEXT,
            concentration INTEGER DEFAULT 0,
            ritual INTEGER DEFAULT 0,
            description TEXT,
            damage TEXT,
            source TEXT DEFAULT 'PHB 2024',
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # SRD 2024 Monsters Library
    "srd_monsters": """
        CREATE TABLE IF NOT EXISTS srd_monsters (
            monster_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            size TEXT,
            alignment TEXT,
            ac INTEGER,
            hp INTEGER,
            str INTEGER DEFAULT 10,
            dex INTEGER DEFAULT 10,
            con INTEGER DEFAULT 10,
            int INTEGER DEFAULT 10,
            wis INTEGER DEFAULT 10,
            cha INTEGER DEFAULT 10,
            challenge_rating REAL DEFAULT 0,
            description TEXT,
            traits TEXT,
            actions TEXT,
            immunities TEXT DEFAULT '',
            resistances TEXT DEFAULT '',
            vulnerabilities TEXT DEFAULT '',
            source TEXT DEFAULT 'MM 2024',
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Weapon Mastery Mapping (2024 rules)
    "weapon_mastery": """
        CREATE TABLE IF NOT EXISTS weapon_mastery (
            weapon_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            weapon_type TEXT,
            mastery_property TEXT,
            dice_damage TEXT,
            range TEXT,
            properties TEXT,
            source TEXT DEFAULT 'PHB 2024',
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Generational System - Session Mode (Architect vs Scribe)
    "dnd_session_mode": """
        CREATE TABLE IF NOT EXISTS dnd_session_mode (
            guild_id TEXT PRIMARY KEY,
            session_mode TEXT DEFAULT 'Architect',
            custom_tone TEXT,
            biome_selection TEXT DEFAULT 'random',
            selected_biome TEXT,
            total_years_elapsed INTEGER DEFAULT 0,
            chronos_enabled INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """,
    
    # Legacy Data - Track Phase 2 characters for Phase 3
    "dnd_legacy_data": """
        CREATE TABLE IF NOT EXISTS dnd_legacy_data (
            legacy_id TEXT PRIMARY KEY,
            guild_id TEXT,
            user_id TEXT,
            p2_character_name TEXT,
            p2_class TEXT,
            signature_move TEXT,
            last_words TEXT,
            legacy_buff TEXT,
            destiny_score INTEGER,
            time_skip_years INTEGER,
            biome_conquered TEXT,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """,
    
    # Soul Remnants - Corrupted echoes of Phase 1/2 characters appearing in Phase 3
    "dnd_soul_remnants": """
        CREATE TABLE IF NOT EXISTS dnd_soul_remnants (
            remnant_id TEXT PRIMARY KEY,
            guild_id TEXT,
            original_user_id TEXT,
            original_character_name TEXT,
            original_phase INTEGER,
            echo_boss_name TEXT,
            echo_boss_stats TEXT,
            soul_remnant_name TEXT,
            soul_remnant_stats TEXT,
            visual_description TEXT,
            appearance_count INTEGER DEFAULT 0,
            defeated INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """,
    
    # Chronicles - Final Phase 3 credits and records
    "dnd_chronicles": """
        CREATE TABLE IF NOT EXISTS dnd_chronicles (
            chronicle_id TEXT PRIMARY KEY,
            guild_id TEXT,
            campaign_name TEXT,
            phase_1_founder TEXT,
            phase_1_founder_id TEXT,
            phase_2_legend TEXT,
            phase_2_legend_id TEXT,
            phase_3_savior TEXT,
            phase_3_savior_id TEXT,
            total_years_elapsed INTEGER,
            total_generations INTEGER,
            biome_name TEXT,
            cycles_broken INTEGER DEFAULT 0,
            eternal_guardians TEXT DEFAULT '[]',
            final_boss_name TEXT,
            victory_date REAL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (guild_id) REFERENCES dnd_config(guild_id) ON DELETE CASCADE
        )
    """
}

# Indexes for better performance
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_dnd_history_thread ON dnd_history (thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_dnd_history_timestamp ON dnd_history (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_dnd_characters_guild ON dnd_characters (guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_dnd_combat_thread ON dnd_combat (thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_reputation_guild ON user_reputation (guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_command_usage_user ON command_usage (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_command_usage_guild ON command_usage (guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_session_tracking_guild ON session_tracking (guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_srd_spells_name ON srd_spells (name)",
    "CREATE INDEX IF NOT EXISTS idx_srd_spells_level ON srd_spells (level)",
    "CREATE INDEX IF NOT EXISTS idx_srd_monsters_name ON srd_monsters (name)",
    "CREATE INDEX IF NOT EXISTS idx_srd_monsters_cr ON srd_monsters (challenge_rating)",
    "CREATE INDEX IF NOT EXISTS idx_weapon_mastery_name ON weapon_mastery (name)"
]

# --- DATABASE INITIALIZATION & MIGRATION ---
class DatabaseManager:
    """Comprehensive database management with automatic migrations"""
    
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.conn = None
    
    def connect(self) -> sqlite3.Connection:
        """Establish database connection with optimizations"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.execute("PRAGMA cache_size = -2000")
        return self.conn
    
    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_database(self) -> None:
        """Initialize all tables and run migrations"""
        print("🛠️  Initializing Database Schema...")
        conn = self.connect()
        cursor = conn.cursor()
        
        # Create all tables
        for table_name, schema in SCHEMA.items():
            cursor.execute(schema)
            print(f"  ✓ Created/Verified table: {table_name}")
        
        # Create indexes
        for index_sql in INDEXES:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                print(f"  ⚠️ Failed to create index: {e}")
        
        # Run migrations on existing tables
        self._run_migrations(cursor)
        
        # Populate default rulebook data
        self._populate_default_rules(cursor)
        
        conn.commit()
        print("💾 Database initialized successfully!")
    
    def _run_migrations(self, cursor: sqlite3.Cursor) -> None:
        """Migrate existing tables to new schema"""
        print("  🔄 Checking for migrations...")
        
        # Check and add missing columns to each table
        tables_to_check = {
            "user_settings": ["language", "created_at", "updated_at"],
            "user_styles": ["style", "created_at", "updated_at"],
            "mod_settings": [
                "log_channel_id", "mod_role_id", "politics_channel_id", 
                "nsfw_channel_id", "gaming_channel_id", "vip_role_id",
                "server_context", "ai_model", "created_at", "updated_at"
            ],
            "user_reputation": [
                "toxicity_score", "last_offense_time", "created_at", "updated_at"
            ],
            "dnd_config": [
                "parent_channel_id", "current_location", "campaign_summary",
                "party_stats", "dnd_role_id", "rulebook", "active_party",
                "campaign_phase", "legends", "game_mode", "quest_data",
                "session_mode", "current_tone", "total_years_elapsed",
                "created_at", "updated_at"
            ],
            "dnd_lore": ["topic", "description", "timestamp", "created_at"],
            "dnd_history": ["thread_id", "role", "content", "timestamp", "metadata"],
            "dnd_characters": ["char_data", "destiny_roll", "created_at", "updated_at"],
            "dnd_combat": [
                "thread_id", "user_id", "name", "init_score", "current_hp",
                "max_hp", "is_monster", "conditions", "created_at", "updated_at"
            ],
            "srd_monsters": [
                "immunities", "resistances", "vulnerabilities"
            ]
        }
        
        for table_name, expected_columns in tables_to_check.items():
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = [col[1] for col in cursor.fetchall()]
                
                for column in expected_columns:
                    if column not in existing_columns:
                        # Determine column type
                        if column in ["created_at", "updated_at", "timestamp", "last_offense_time"]:
                            col_type = "REAL DEFAULT (strftime('%s', 'now'))"
                        elif column in ["toxicity_score", "campaign_phase", "destiny_roll", 
                                      "init_score", "current_hp", "max_hp", "is_monster",
                                      "total_years_elapsed"]:
                            col_type = "INTEGER DEFAULT 0"
                        elif column == "metadata":
                            col_type = "TEXT DEFAULT '{}'"
                        elif column == "session_mode":
                            col_type = "TEXT DEFAULT 'Architect'"
                        elif column == "current_tone":
                            col_type = "TEXT DEFAULT 'Standard'"
                        elif column in ["immunities", "resistances", "vulnerabilities"]:
                            col_type = "TEXT DEFAULT ''"
                        else:
                            col_type = "TEXT"
                        
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {col_type}")
                            print(f"    ✓ Added column {column} to {table_name}")
                        except sqlite3.OperationalError as e:
                            print(f"    ⚠️ Failed to add {column} to {table_name}: {e}")
            except sqlite3.OperationalError:
                # Table doesn't exist yet (will be created by schema)
                pass
        
        # Ensure foreign keys are enabled
        cursor.execute("PRAGMA foreign_keys = ON")
    
    def _populate_default_rules(self, cursor: sqlite3.Cursor) -> None:
        """Populate default D&D rulebook entries"""
        try:
            cursor.execute("SELECT COUNT(*) FROM dnd_rulebook")
            if cursor.fetchone()[0] == 0:
                default_rules = [
                    ("fireball", "3rd-level evocation. Casting Time: 1 action. Range: 150 feet. Components: V, S, M. Duration: Instantaneous. Each creature in a 20-foot-radius sphere must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much on a success.", "spell", "PHB 2024"),
                    ("attack", "When you take the Attack action, you can make one weapon attack. Add your proficiency bonus to attack rolls with weapons you are proficient with.", "action", "PHB 2024"),
                    ("saving throw", "A saving throw represents an attempt to resist a spell, trap, poison, disease, or similar threat. The DC (Difficulty Class) determines how hard it is to resist. Roll d20 + ability modifier + proficiency (if proficient).", "mechanic", "PHB 2024"),
                    ("concentration", "When you cast a spell that requires concentration, you must maintain concentration to keep it active. You lose concentration if: you cast another concentration spell, you take damage (DC 10 or half damage, whichever is higher), you are incapacitated or killed.", "mechanic", "PHB 2024"),
                    ("short rest", "A short rest is a period of downtime, at least 1 hour long. A character can spend one or more Hit Dice to regain hit points.", "rest", "PHB 2024"),
                    ("long rest", "A long rest is a period of extended downtime, at least 8 hours long. At the end of a long rest, a character regains all lost hit points and half their total Hit Dice (minimum 1).", "rest", "PHB 2024"),
                    ("advantage", "When you have advantage, roll two d20s and take the higher result. When you have disadvantage, roll two d20s and take the lower result.", "mechanic", "PHB 2024"),
                    ("heroic_inspiration", "Heroic Inspiration is a special reward given by the DM. A character with Heroic Inspiration can reroll one d20 after seeing the result, taking the new roll.", "mechanic", "PHB 2024"),
                    ("death saving throw", "When you start your turn with 0 hit points, you must make a death saving throw. Roll a d20: 10 or higher = success, 9 or lower = failure. 3 successes = stable, 3 failures = dead. Natural 1 = 2 failures. Natural 20 = regain 1 HP.", "mechanic", "PHB 2024"),
                    ("stealth", "Make a Dexterity (Stealth) check when you attempt to conceal yourself, move silently, or avoid detection. Opposed by Wisdom (Perception) checks.", "skill", "PHB 2024"),
                    ("species", "Character species (2024 rules) determines certain biological traits. Choose from options like Human, Elf, Dwarf, Halfling, etc.", "character", "PHB 2024"),
                    ("background", "A character's background provides skill proficiencies, tool proficiencies, equipment, and a feature that can aid in roleplaying.", "character", "PHB 2024"),
                ]
                
                cursor.executemany(
                    "INSERT INTO dnd_rulebook (keyword, rule_text, rule_type, source) VALUES (?, ?, ?, ?)",
                    default_rules
                )
                print("    ✓ Populated default D&D rules")
        except sqlite3.Error as e:
            print(f"    ⚠️ Error populating default rules: {e}")

# --- USER SETTINGS FUNCTIONS ---
def save_user_language(user_id: int, language: str) -> None:
    """Save user's preferred language"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, language, updated_at) VALUES (?, ?, ?)",
        (str(user_id), language, time.time())
    )
    conn.commit()
    conn.close()
    clear_cache(f"user_lang_{user_id}")

def save_user_style(user_id: int, style: str) -> None:
    """Save user's preferred style"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_styles (user_id, style, updated_at) VALUES (?, ?, ?)",
        (str(user_id), style, time.time())
    )
    conn.commit()
    conn.close()
    clear_cache(f"user_style_{user_id}")

def get_target_language(user_id: int, default: str = "English") -> str:
    """Get user's preferred language with caching"""
    cache_key = f"user_lang_{user_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT language FROM user_settings WHERE user_id=?", (str(user_id),))
    result = c.fetchone()
    conn.close()
    
    lang = result[0] if result else default
    set_cache(cache_key, lang)
    return lang

def get_user_global_style(user_id: int) -> str:
    """Get user's preferred style with caching"""
    cache_key = f"user_style_{user_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT style FROM user_styles WHERE user_id=?", (str(user_id),))
    result = c.fetchone()
    conn.close()
    
    style = result[0] if result else "Slang/Chat"
    set_cache(cache_key, style)
    return style

# --- MODERATION FUNCTIONS ---
def get_mod_settings(guild_id: int) -> Optional[Tuple]:
    """Get moderation settings for a guild"""
    cache_key = f"mod_settings_{guild_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT log_channel_id, mod_role_id, politics_channel_id, nsfw_channel_id, "
        "gaming_channel_id, vip_role_id, server_context, ai_model FROM mod_settings WHERE guild_id=?",
        (str(guild_id),)
    )
    result = c.fetchone()
    conn.close()
    
    if result:
        # Convert "None" strings to None
        result = tuple(None if val == "None" else val for val in result)
    set_cache(cache_key, result)
    return result

def save_mod_settings(guild_id: int, **kwargs) -> None:
    """Save moderation settings"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if guild exists
    c.execute("SELECT 1 FROM mod_settings WHERE guild_id=?", (str(guild_id),))
    exists = c.fetchone()
    
    if exists:
        # Update existing
        set_clause = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                set_clause.append(f"{key}=?")
                values.append(str(value.id) if hasattr(value, 'id') else str(value))
        values.append(str(guild_id))
        
        if set_clause:
            c.execute(
                f"UPDATE mod_settings SET {', '.join(set_clause)}, updated_at=? WHERE guild_id=?",
                values + [time.time(), str(guild_id)]
            )
    else:
        # Insert new
        columns = ["guild_id"]
        placeholders = ["?"]
        col_values = [str(guild_id)]
        
        for key, value in kwargs.items():
            if value is not None:
                columns.append(key)
                placeholders.append("?")
                col_values.append(str(value.id) if hasattr(value, 'id') else str(value))
        
        columns.append("created_at")
        placeholders.append("?")
        col_values.append(time.time())
        
        c.execute(
            f"INSERT INTO mod_settings ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
            col_values
        )
    
    conn.commit()
    conn.close()
    clear_cache(f"mod_settings_{guild_id}")

def get_vip_role_id(guild_id: int) -> Optional[str]:
    """Get VIP role ID for a guild"""
    cache_key = f"vip_role_{guild_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT vip_role_id FROM mod_settings WHERE guild_id=?", (str(guild_id),))
    result = c.fetchone()
    conn.close()
    
    vip_id = result[0] if result and result[0] and result[0] != "None" else None
    set_cache(cache_key, vip_id)
    return vip_id

def get_server_model_name(guild_id: int) -> str:
    """Get AI model name for a server"""
    cache_key = f"server_model_{guild_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT ai_model FROM mod_settings WHERE guild_id=?", (str(guild_id),))
    result = c.fetchone()
    conn.close()
    
    model = result[0] if result and result[0] and result[0] != "None" else 'models/gemma-3-27b-it'
    set_cache(cache_key, model)
    return model

# --- REPUTATION SYSTEM ---
def update_user_reputation(user_id: int, guild_id: int, points: int) -> int:
    """Update user's reputation score and return new score"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get current score
    c.execute(
        "SELECT toxicity_score, last_offense_time FROM user_reputation WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id))
    )
    result = c.fetchone()
    now = time.time()
    
    if result:
        score, last_time = result
        # Decay: heal 2 points per hour since last offense
        decay = int((now - last_time) / 3600) * 2
        new_score = max(0, score - decay) + points
    else:
        new_score = points
    
    # Update or insert
    c.execute(
        """INSERT OR REPLACE INTO user_reputation 
           (user_id, guild_id, toxicity_score, last_offense_time, updated_at) 
           VALUES (?, ?, ?, ?, ?)""",
        (str(user_id), str(guild_id), new_score, now, now)
    )
    
    conn.commit()
    conn.close()
    return new_score

def get_user_reputation(user_id: int, guild_id: int) -> int:
    """Get user's current reputation score with decay calculation"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT toxicity_score, last_offense_time FROM user_reputation WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id))
    )
    result = c.fetchone()
    conn.close()
    
    if not result:
        return 0
    
    score, last_time = result
    now = time.time()
    decay = int((now - last_time) / 3600) * 2
    return max(0, score - decay)

# --- D&D CONFIGURATION FUNCTIONS ---
def save_dnd_config(guild_id: int, parent_channel_id: int, dnd_role_id: Optional[int] = None) -> None:
    """Save D&D configuration"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if exists
    c.execute("SELECT 1 FROM dnd_config WHERE guild_id=?", (str(guild_id),))
    exists = c.fetchone()
    
    if exists:
        # Update
        updates = ["parent_channel_id=?", "updated_at=?"]
        values = [str(parent_channel_id), time.time()]
        
        if dnd_role_id:
            updates.append("dnd_role_id=?")
            values.append(str(dnd_role_id))
        
        values.append(str(guild_id))
        c.execute(f"UPDATE dnd_config SET {', '.join(updates)} WHERE guild_id=?", values)
    else:
        # Insert
        columns = ["guild_id", "parent_channel_id", "created_at"]
        placeholders = ["?", "?", "?"]
        col_values = [str(guild_id), str(parent_channel_id), time.time()]
        
        if dnd_role_id:
            columns.append("dnd_role_id")
            placeholders.append("?")
            col_values.append(str(dnd_role_id))
        
        c.execute(
            f"INSERT INTO dnd_config ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
            col_values
        )
    
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def get_dnd_config(guild_id: int) -> Optional[Tuple]:
    """Get D&D configuration"""
    cache_key = f"dnd_config_{guild_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """SELECT parent_channel_id, current_location, campaign_summary, party_stats, 
                  dnd_role_id, rulebook, active_party, campaign_phase, legends, 
                  game_mode, quest_data FROM dnd_config WHERE guild_id=?""",
        (str(guild_id),)
    )
    result = c.fetchone()
    conn.close()
    
    set_cache(cache_key, result)
    return result

def update_dnd_location(guild_id: int, location: str) -> None:
    """Update current location"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET current_location=?, updated_at=? WHERE guild_id=?",
        (location, time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def update_dnd_summary(guild_id: int, summary: str) -> None:
    """Update campaign summary"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET campaign_summary=?, updated_at=? WHERE guild_id=?",
        (summary, time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def update_dnd_rulebook(guild_id: int, rulebook: str) -> None:
    """Update rulebook"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET rulebook=?, updated_at=? WHERE guild_id=?",
        (rulebook, time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def update_game_mode(guild_id: int, mode: str) -> None:
    """Update game mode"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET game_mode=?, updated_at=? WHERE guild_id=?",
        (mode, time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def save_active_party(guild_id: int, user_ids: List[int]) -> None:
    """Save active party members"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET active_party=?, updated_at=? WHERE guild_id=?",
        (json.dumps(user_ids), time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def update_quest_data(guild_id: int, quest_data: Dict) -> None:
    """Update quest data"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET quest_data=?, updated_at=? WHERE guild_id=?",
        (json.dumps(quest_data), time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def get_dnd_campaign_data(guild_id: int) -> Tuple[int, List]:
    """Get campaign phase and legends"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT campaign_phase, legends FROM dnd_config WHERE guild_id=?",
        (str(guild_id),)
    )
    r = c.fetchone()
    conn.close()
    
    if r:
        try:
            phase = r[0] if r[0] is not None and r[0] > 0 else 1
            legends_data = json.loads(r[1]) if r[1] else []
            return phase, legends_data
        except:
            return 1, []
    return 1, []

def advance_campaign_phase(guild_id: int, new_phase: int, legends: List) -> None:
    """Advance campaign phase"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_config SET campaign_phase=?, legends=?, updated_at=? WHERE guild_id=?",
        (new_phase, json.dumps(legends), time.time(), str(guild_id))
    )
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def reset_campaign(guild_id: int, thread_id: int) -> None:
    """Reset campaign data"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Reset config
    c.execute(
        """UPDATE dnd_config SET 
           current_location='tavern', 
           campaign_summary='New Campaign Started.',
           campaign_phase=1, 
           active_party='[]', 
           game_mode='Narrative', 
           quest_data=NULL, 
           legends='[]',
           updated_at=? 
           WHERE guild_id=?""",
        (time.time(), str(guild_id))
    )
    
    # Clear history
    c.execute("DELETE FROM dnd_history WHERE thread_id=?", (str(thread_id),))
    
    # Clear combat
    c.execute("DELETE FROM dnd_combat WHERE thread_id=?", (str(thread_id),))
    
    # Clear destiny roll lore
    c.execute(
        "DELETE FROM dnd_lore WHERE guild_id=? AND description LIKE 'Destiny Roll %'",
        (str(guild_id),)
    )
    
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

# --- D&D HISTORY FUNCTIONS ---
def add_dnd_history(thread_id: int, role: str, content: str, metadata: Optional[Dict] = None) -> None:
    """Add entry to D&D history"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO dnd_history (thread_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
        (str(thread_id), role, content, time.time(), json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()

def get_dnd_history(thread_id: int, limit: int = 10) -> List[Tuple[str, str]]:
    """Get D&D history for a thread"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT role, content FROM dnd_history WHERE thread_id=? ORDER BY timestamp DESC LIMIT ?",
        (str(thread_id), limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows[::-1]

def add_lore(guild_id: int, topic: str, description: str) -> None:
    """Add lore entry"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO dnd_lore (guild_id, topic, description, timestamp) VALUES (?, ?, ?, ?)",
        (str(guild_id), topic, description, time.time())
    )
    conn.commit()
    conn.close()

def get_lore(guild_id: int, limit: int = 50) -> List[Tuple[str, str]]:
    """Get lore entries"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT topic, description FROM dnd_lore WHERE guild_id=? ORDER BY timestamp DESC LIMIT ?",
        (str(guild_id), limit)
    )
    r = c.fetchall()
    conn.close()
    return r

# --- CHARACTER MANAGEMENT ---
def update_character(user_id: int, guild_id: int, char_data: Dict) -> None:
    """Update or create character"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO dnd_characters 
           (user_id, guild_id, char_data, updated_at) VALUES (?, ?, ?, ?)""",
        (str(user_id), str(guild_id), json.dumps(char_data), time.time())
    )
    conn.commit()
    conn.close()

def get_character(user_id: int, guild_id: int) -> Optional[Dict]:
    """Get character data"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT char_data FROM dnd_characters WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id))
    )
    r = c.fetchone()
    conn.close()
    return json.loads(r[0]) if r else None

def batch_update_destiny(guild_id: int, user_rolls: Dict[int, int]) -> None:
    """Batch update destiny rolls"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for uid, roll in user_rolls.items():
        c.execute(
            "UPDATE dnd_characters SET destiny_roll=?, updated_at=? WHERE user_id=? AND guild_id=?",
            (roll, time.time(), str(uid), str(guild_id))
        )
    conn.commit()
    conn.close()

def update_character_destiny(user_id: int, guild_id: int, roll: int) -> None:
    """Update character destiny roll"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "UPDATE dnd_characters SET destiny_roll=?, updated_at=? WHERE user_id=? AND guild_id=?",
        (roll, time.time(), str(user_id), str(guild_id))
    )
    conn.commit()
    conn.close()

def get_session_protagonist(guild_id: int) -> Tuple[Optional[str], int]:
    """Get session protagonist based on highest destiny roll"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT char_data, destiny_roll FROM dnd_characters WHERE guild_id=? ORDER BY destiny_roll DESC LIMIT 1",
        (str(guild_id),)
    )
    r = c.fetchone()
    conn.close()
    
    if r and r[1] and r[1] > 0:
        try:
            char_data = json.loads(r[0])
            return char_data.get('name', 'Unknown'), r[1]
        except:
            return None, 0
    return None, 0

# --- COMBAT MANAGEMENT ---
def add_combatant(
    thread_id: int, 
    user_id: int, 
    name: str, 
    score: int, 
    hp: int = 0, 
    max_hp: int = 0, 
    is_monster: int = 0
) -> None:
    """Add combatant to combat"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO dnd_combat 
           (thread_id, user_id, name, init_score, current_hp, max_hp, is_monster, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(thread_id), str(user_id), name, score, hp, max_hp, is_monster, time.time())
    )
    conn.commit()
    conn.close()

def add_monster_combatant(thread_id: int, name: str, score: int, hp: int, max_hp: int) -> str:
    """Add monster combatant with generated ID"""
    monster_id = f"npc_{name.replace(' ', '_')}_{int(time.time()*1000)}_{random.randint(100,999)}"
    add_combatant(thread_id, monster_id, name, score, hp, max_hp, is_monster=1)
    return monster_id

def update_combatant_hp(thread_id: int, user_id: int, hp_change: int) -> Optional[int]:
    """Update combatant HP and return new HP"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT current_hp, max_hp FROM dnd_combat WHERE thread_id=? AND user_id=?",
        (str(thread_id), str(user_id))
    )
    row = c.fetchone()
    
    if row:
        curr, m_hp = row
        new_hp = max(0, min(m_hp, curr + hp_change))
        c.execute(
            "UPDATE dnd_combat SET current_hp=?, updated_at=? WHERE thread_id=? AND user_id=?",
            (new_hp, time.time(), str(thread_id), str(user_id))
        )
        conn.commit()
        conn.close()
        return new_hp
    
    conn.close()
    return None

def update_combatant_condition(thread_id: int, user_id: int, condition: str, remove: bool = False) -> None:
    """Update combatant conditions"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT conditions FROM dnd_combat WHERE thread_id=? AND user_id=?",
        (str(thread_id), str(user_id))
    )
    row = c.fetchone()
    
    if row:
        curr_str = row[0] if row[0] else ""
        conds = [x.strip() for x in curr_str.split(',') if x.strip()]
        
        if remove:
            if condition in conds:
                conds.remove(condition)
        else:
            if condition not in conds:
                conds.append(condition)
        
        c.execute(
            "UPDATE dnd_combat SET conditions=?, updated_at=? WHERE thread_id=? AND user_id=?",
            (", ".join(conds), time.time(), str(thread_id), str(user_id))
        )
        conn.commit()
    conn.close()

def get_combatant_conditions(thread_id: int, user_id: int) -> str:
    """Get combatant conditions"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT conditions FROM dnd_combat WHERE thread_id=? AND user_id=?",
        (str(thread_id), str(user_id))
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def remove_combatant(thread_id: int, user_id: int) -> None:
    """Remove combatant"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "DELETE FROM dnd_combat WHERE thread_id=? AND user_id=?",
        (str(thread_id), str(user_id))
    )
    conn.commit()
    conn.close()

def get_combat_order(thread_id: int) -> List[Tuple]:
    """Get combat order"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """SELECT user_id, name, init_score, current_hp, max_hp, is_monster, conditions 
           FROM dnd_combat WHERE thread_id=? ORDER BY init_score DESC""",
        (str(thread_id),)
    )
    r = c.fetchall()
    conn.close()
    return r

def clear_combat(thread_id: int) -> None:
    """Clear all combatants from thread"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM dnd_combat WHERE thread_id=?", (str(thread_id),))
    conn.commit()
    conn.close()

def perform_long_rest_db(thread_id: int, guild_id: int) -> None:
    """Perform long rest - heal all players"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Heal all player combatants
    c.execute(
        "SELECT user_id FROM dnd_combat WHERE thread_id=? AND is_monster=0",
        (str(thread_id),)
    )
    players = c.fetchall()
    
    for (uid,) in players:
        # Reset HP and conditions
        c.execute(
            "UPDATE dnd_combat SET current_hp=max_hp, conditions='', updated_at=? WHERE thread_id=? AND user_id=?",
            (time.time(), str(thread_id), uid)
        )
        
        # Update character sheet
        c.execute(
            "SELECT char_data FROM dnd_characters WHERE user_id=? AND guild_id=?",
            (uid, str(guild_id))
        )
        row = c.fetchone()
        
        if row:
            try:
                data = json.loads(row[0])
                data['hp'] = data.get('max_hp', 10)
                data['heroic_inspiration'] = True
                data['has_inspiration'] = True  # Legacy support
                c.execute(
                    "UPDATE dnd_characters SET char_data=?, updated_at=? WHERE user_id=? AND guild_id=?",
                    (json.dumps(data), time.time(), uid, str(guild_id))
                )
            except:
                pass
    
    conn.commit()
    conn.close()

# --- RULEBOOK MANAGEMENT ---
def add_rule(keyword: str, rule_text: str, rule_type: str = "custom", source: str = "DM") -> None:
    """Add or update rule in rulebook"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO dnd_rulebook 
           (keyword, rule_text, rule_type, source, updated_at) VALUES (?, ?, ?, ?, ?)""",
        (keyword.lower(), rule_text, rule_type, source, time.time())
    )
    conn.commit()
    conn.close()

def lookup_rule(keyword: str, limit: int = 3) -> List[Tuple[str, str]]:
    """Look up rules by keyword"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """SELECT keyword, rule_text FROM dnd_rulebook 
           WHERE keyword LIKE ? OR rule_text LIKE ? LIMIT ?""",
        (f"%{keyword}%", f"%{keyword}%", limit)
    )
    results = c.fetchall()
    conn.close()
    return results

# --- SESSION TRACKING ---
def start_session(session_id: str, guild_id: int, thread_id: int) -> None:
    """Start tracking a session"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT INTO session_tracking 
           (session_id, guild_id, thread_id, start_time) VALUES (?, ?, ?, ?)""",
        (session_id, str(guild_id), str(thread_id), time.time())
    )
    conn.commit()
    conn.close()

def end_session(session_id: str, summary: Optional[str] = None) -> None:
    """End a session and record summary"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get start time
    c.execute("SELECT start_time FROM session_tracking WHERE session_id=?", (session_id,))
    result = c.fetchone()
    
    if result:
        duration = int(time.time() - result[0])
        c.execute(
            """UPDATE session_tracking SET 
               end_time=?, duration=?, summary=? WHERE session_id=?""",
            (time.time(), duration, summary, session_id)
        )
    
    conn.commit()
    conn.close()

def record_command_usage(user_id: int, guild_id: int, command: str, success: bool = True, error: Optional[str] = None) -> None:
    """Record command usage for analytics"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT INTO command_usage 
           (user_id, guild_id, command, success, error_message, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(user_id), str(guild_id), command, 1 if success else 0, error, time.time())
    )
    conn.commit()
    conn.close()

# --- DATABASE MAINTENANCE ---
def vacuum_database() -> None:
    """Compact and optimize database"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("VACUUM")
    conn.close()
    clear_all_cache()
    print("🧹 Database vacuumed and optimized")

def backup_database(backup_path: str) -> None:
    """Create database backup"""
    import shutil
    try:
        shutil.copy2(DB_FILE, backup_path)
        print(f"💾 Database backed up to {backup_path}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")

# --- SRD 2024 QUERY FUNCTIONS ---
def get_spell_by_name(spell_name: str) -> Optional[Dict]:
    """Get spell details by name"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT spell_id, name, level, school, casting_time, range, 
                        duration, description, damage, concentration
                 FROM srd_spells WHERE name LIKE ? LIMIT 1""", 
             (f"%{spell_name}%",))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            "id": result[0], "name": result[1], "level": result[2],
            "school": result[3], "casting_time": result[4], "range": result[5],
            "duration": result[6], "description": result[7], "damage": result[8],
            "concentration": bool(result[9])
        }
    return None

def search_spells_by_level(level: int, limit: int = 10) -> List[Dict]:
    """Search spells by spell level"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT spell_id, name, level, school, damage 
                 FROM srd_spells WHERE level = ? LIMIT ?""",
             (level, limit))
    
    results = c.fetchall()
    conn.close()
    
    return [{"id": r[0], "name": r[1], "level": r[2], "school": r[3], "damage": r[4]} 
            for r in results]

def get_monster_by_name(monster_name: str) -> Optional[Dict]:
    """Get monster details by name with immunities/resistances/vulnerabilities"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT monster_id, name, type, size, alignment, ac, hp, 
                        str, dex, con, int, wis, cha, challenge_rating, 
                        description, traits, actions, immunities, resistances, vulnerabilities
                 FROM srd_monsters WHERE name LIKE ? LIMIT 1""",
             (f"%{monster_name}%",))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            "id": result[0], "name": result[1], "type": result[2], "size": result[3],
            "alignment": result[4], "ac": result[5], "hp": result[6],
            "abilities": {"str": result[7], "dex": result[8], "con": result[9], 
                         "int": result[10], "wis": result[11], "cha": result[12]},
            "cr": result[13], "description": result[14],
            "traits": result[15] if len(result) > 15 else "",
            "actions": result[16] if len(result) > 16 else "",
            "immunities": result[17] if len(result) > 17 else "",
            "resistances": result[18] if len(result) > 18 else "",
            "vulnerabilities": result[19] if len(result) > 19 else ""
        }
    return None

def search_monsters_by_cr(cr_min: float, cr_max: float, limit: int = 10) -> List[Dict]:
    """Search monsters by challenge rating"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT monster_id, name, size, challenge_rating, ac, hp 
                 FROM srd_monsters WHERE challenge_rating BETWEEN ? AND ? 
                 ORDER BY challenge_rating ASC LIMIT ?""",
             (cr_min, cr_max, limit))
    
    results = c.fetchall()
    conn.close()
    
    return [{"id": r[0], "name": r[1], "size": r[2], "cr": r[3], "ac": r[4], "hp": r[5]} 
            for r in results]

def get_weapon_mastery(weapon_name: str) -> Optional[Dict]:
    """Get weapon mastery property for 2024 rules"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT weapon_id, name, weapon_type, mastery_property, 
                        dice_damage, range, properties
                 FROM weapon_mastery WHERE name LIKE ? LIMIT 1""",
             (f"%{weapon_name}%",))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            "id": result[0], "name": result[1], "type": result[2],
            "mastery": result[3], "damage": result[4], "range": result[5],
            "properties": result[6].split(", ") if result[6] else []
        }
    return None

def search_weapons_by_type(weapon_type: str, limit: int = 20) -> List[Dict]:
    """Search weapons by type (simple_melee, martial_ranged, etc.)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT weapon_id, name, mastery_property, damage, range
                 FROM weapon_mastery WHERE weapon_type = ? LIMIT ?""",
             (weapon_type, limit))
    
    results = c.fetchall()
    conn.close()
    
    return [{"id": r[0], "name": r[1], "mastery": r[2], "damage": r[3], "range": r[4]} 
            for r in results]


# --- GENERATIONAL SYSTEM FUNCTIONS ---

def save_session_mode(guild_id: int, session_mode: str = "Architect", 
                     biome: Optional[str] = None, custom_tone: Optional[str] = None) -> None:
    """Save session mode (Architect vs Scribe)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""INSERT OR REPLACE INTO dnd_session_mode 
                (guild_id, session_mode, selected_biome, custom_tone, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
             (str(guild_id), session_mode, biome, custom_tone, time.time()))
    
    conn.commit()
    conn.close()
    clear_cache(f"session_mode_{guild_id}")

def get_session_mode(guild_id: int) -> Optional[Tuple]:
    """Get session mode configuration"""
    cache_key = f"session_mode_{guild_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT session_mode, custom_tone, selected_biome, total_years_elapsed, chronos_enabled
                 FROM dnd_session_mode WHERE guild_id=?""",
             (str(guild_id),))
    result = c.fetchone()
    conn.close()
    
    set_cache(cache_key, result)
    return result

def update_session_tone(guild_id: int, tone: str) -> None:
    """Update current session tone (for Architect mode automatic shifting)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""UPDATE dnd_config SET current_tone=?, updated_at=? WHERE guild_id=?""",
             (tone, time.time(), str(guild_id)))
    
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def save_legacy_data(guild_id: int, user_id: int, character_name: str, 
                    legacy_data: Dict) -> str:
    """Save a Phase 2 character as legacy for Phase 3"""
    legacy_id = f"legacy_{guild_id}_{user_id}_{int(time.time())}"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""INSERT INTO dnd_legacy_data 
                (legacy_id, guild_id, user_id, p2_character_name, p2_class, 
                 signature_move, last_words, legacy_buff, destiny_score, 
                 time_skip_years, biome_conquered, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
             (legacy_id, str(guild_id), str(user_id), character_name,
              legacy_data.get('class', 'Unknown'),
              legacy_data.get('signature_move', ''),
              legacy_data.get('last_words', ''),
              legacy_data.get('legacy_buff', ''),
              legacy_data.get('destiny_score', 0),
              legacy_data.get('time_skip_years', 0),
              legacy_data.get('biome_conquered', 'unknown'),
              time.time()))
    
    conn.commit()
    conn.close()
    
    return legacy_id

def get_legacy_data(guild_id: int, user_id: Optional[int] = None) -> Optional[List[Tuple]]:
    """Get legacy data for a guild or specific user"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if user_id:
        c.execute("""SELECT legacy_id, p2_character_name, p2_class, legacy_buff, 
                           destiny_score, time_skip_years, biome_conquered
                     FROM dnd_legacy_data WHERE guild_id=? AND user_id=?
                     ORDER BY created_at DESC""",
                 (str(guild_id), str(user_id)))
    else:
        c.execute("""SELECT legacy_id, user_id, p2_character_name, p2_class, legacy_buff, 
                           destiny_score, time_skip_years, biome_conquered
                     FROM dnd_legacy_data WHERE guild_id=?
                     ORDER BY created_at DESC LIMIT 20""",
                 (str(guild_id),))
    
    results = c.fetchall()
    conn.close()
    
    return results if results else None

def save_soul_remnant(guild_id: int, legacy_data: Dict, echo_boss: Dict, 
                     soul_remnant: Dict) -> str:
    """Save a soul remnant (corrupted Phase 1/2 PC for Phase 3)"""
    remnant_id = f"remnant_{guild_id}_{int(time.time())}"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""INSERT INTO dnd_soul_remnants
                (remnant_id, guild_id, original_user_id, original_character_name,
                 original_phase, echo_boss_name, echo_boss_stats, soul_remnant_name,
                 soul_remnant_stats, visual_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
             (remnant_id, str(guild_id), str(legacy_data.get('user_id', '')),
              legacy_data.get('p2_character_name', 'Unknown'),
              2,
              echo_boss.get('name', 'Echo'),
              json.dumps(echo_boss),
              soul_remnant.get('name', 'Soul Remnant'),
              json.dumps(soul_remnant),
              soul_remnant.get('visual_desc', ''),
              time.time()))
    
    conn.commit()
    conn.close()
    
    return remnant_id

def get_soul_remnants(guild_id: int) -> Optional[List[Tuple]]:
    """Get all soul remnants for a guild"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT remnant_id, original_character_name, echo_boss_name,
                        soul_remnant_name, visual_description, defeated
                 FROM dnd_soul_remnants WHERE guild_id=? AND defeated=0
                 ORDER BY created_at DESC""",
             (str(guild_id),))
    
    results = c.fetchall()
    conn.close()
    
    return results if results else None

def mark_remnant_defeated(remnant_id: str) -> None:
    """Mark a soul remnant as defeated"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""UPDATE dnd_soul_remnants SET defeated=1 WHERE remnant_id=?""",
             (remnant_id,))
    
    conn.commit()
    conn.close()

def save_chronicles(guild_id: int, chronicles_data: Dict) -> str:
    """Save final Phase 3 chronicles (victory scroll)"""
    chronicle_id = f"chronicle_{guild_id}_{int(time.time())}"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""INSERT INTO dnd_chronicles
                (chronicle_id, guild_id, campaign_name, phase_1_founder,
                 phase_1_founder_id, phase_2_legend, phase_2_legend_id,
                 phase_3_savior, phase_3_savior_id, total_years_elapsed,
                 total_generations, biome_name, cycles_broken, eternal_guardians,
                 final_boss_name, victory_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
             (chronicle_id, str(guild_id), chronicles_data.get('campaign_name', 'Legacy Campaign'),
              chronicles_data.get('phase_1_founder', 'Unknown'),
              str(chronicles_data.get('phase_1_founder_id', '')),
              chronicles_data.get('phase_2_legend', 'Unknown'),
              str(chronicles_data.get('phase_2_legend_id', '')),
              chronicles_data.get('phase_3_savior', 'Unknown'),
              str(chronicles_data.get('phase_3_savior_id', '')),
              chronicles_data.get('total_years_elapsed', 0),
              chronicles_data.get('total_generations', 1),
              chronicles_data.get('biome_name', 'Unknown'),
              chronicles_data.get('cycles_broken', 0),
              json.dumps(chronicles_data.get('eternal_guardians', [])),
              chronicles_data.get('final_boss_name', 'The Void'),
              time.time(),
              time.time()))
    
    conn.commit()
    conn.close()
    
    return chronicle_id

def get_chronicles(guild_id: int) -> Optional[Tuple]:
    """Get chronicles for a guild"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT chronicle_id, campaign_name, phase_1_founder, phase_2_legend,
                        phase_3_savior, total_years_elapsed, total_generations,
                        biome_name, eternal_guardians, final_boss_name, victory_date
                 FROM dnd_chronicles WHERE guild_id=?
                 ORDER BY victory_date DESC LIMIT 1""",
             (str(guild_id),))
    
    result = c.fetchone()
    conn.close()
    
    return result

def update_total_years(guild_id: int, additional_years: int) -> int:
    """Update total years elapsed and return new total"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get current total
    c.execute("SELECT total_years_elapsed FROM dnd_config WHERE guild_id=?",
             (str(guild_id),))
    result = c.fetchone()
    current_total = result[0] if result else 0
    
    new_total = current_total + additional_years
    
    c.execute("""UPDATE dnd_config SET total_years_elapsed=?, updated_at=?
                WHERE guild_id=?""",
             (new_total, time.time(), str(guild_id)))
    
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")
    
    return new_total

# --- COG INTEGRATION ---

class DatabaseCog(commands.Cog):
    """Discord cog for database management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
    
    async def cog_load(self):
        """Initialize database on cog load"""
        self.db_manager.initialize_database()
        print("✅ Database cog loaded")
    
    @commands.command(name="dbstats", hidden=True)
    @commands.is_owner()
    async def db_stats(self, ctx):
        """Show database statistics (Owner only)"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        embed = discord.Embed(title="📊 Database Statistics", color=0x3498DB)
        
        # Table row counts
        tables = [
            "user_settings", "user_styles", "mod_settings", "user_reputation",
            "dnd_config", "dnd_lore", "dnd_history", "dnd_characters",
            "dnd_combat", "dnd_rulebook", "command_usage", "session_tracking"
        ]
        
        for table in tables:
            try:
                c.execute(f"SELECT COUNT(*) FROM {table}")
                count = c.fetchone()[0]
                embed.add_field(name=table, value=str(count), inline=True)
            except:
                embed.add_field(name=table, value="N/A", inline=True)
        
        # Database size
        size_mb = os.path.getsize(DB_FILE) / (1024 * 1024)
        embed.add_field(name="Database Size", value=f"{size_mb:.2f} MB", inline=False)
        
        # Cache stats
        embed.add_field(name="Cache Items", value=str(len(_cache)), inline=True)
        
        conn.close()
        await ctx.send(embed=embed)
    
    @commands.command(name="dbvacuum", hidden=True)
    @commands.is_owner()
    async def db_vacuum(self, ctx):
        """Vacuum database (Owner only)"""
        await ctx.send("🧹 Vacuuming database...")
        vacuum_database()
        await ctx.send("✅ Database optimized")
    
    @commands.command(name="dbbackup", hidden=True)
    @commands.is_owner()
    async def db_backup(self, ctx, filename: str = None):
        """Backup database (Owner only)"""
        if filename is None:
            filename = f"backup_{int(time.time())}.db"
        
        backup_path = os.path.join(os.path.dirname(DB_FILE), filename)
        backup_database(backup_path)
        
        await ctx.send(f"✅ Database backed up to `{filename}`")

def save_void_cycle_data(guild_id: int, phase: int, world_unique_point: str = None, generation: int = None) -> None:
    """Save Void Cycle campaign data (phase, unique point, generation)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get current config
    c.execute("SELECT * FROM dnd_config WHERE guild_id=?", (str(guild_id),))
    exists = c.fetchone()
    
    if exists:
        updates = []
        values = []
        
        if phase is not None:
            updates.append("campaign_phase=?")
            values.append(phase)
        
        if world_unique_point is not None:
            updates.append("world_unique_point=?")
            values.append(world_unique_point)
        
        if generation is not None:
            updates.append("generation=?")
            values.append(generation)
        
        updates.append("updated_at=?")
        values.append(time.time())
        values.append(str(guild_id))
        
        c.execute(f"UPDATE dnd_config SET {', '.join(updates)} WHERE guild_id=?", values)
    else:
        # Create new config row
        c.execute(
            """INSERT INTO dnd_config 
               (guild_id, campaign_phase, world_unique_point, generation, updated_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (str(guild_id), phase or 1, world_unique_point, generation or 1, time.time())
        )
    
    conn.commit()
    conn.close()
    clear_cache(f"dnd_config_{guild_id}")

def get_void_cycle_data(guild_id: int) -> Tuple[int, str, int]:
    """Get Void Cycle data: (phase, world_unique_point, generation)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "SELECT campaign_phase, world_unique_point, generation FROM dnd_config WHERE guild_id=?",
            (str(guild_id),)
        )
        result = c.fetchone()
        conn.close()
        
        if result:
            return result[0] or 1, result[1] or "uninitialized", result[2] or 1
        return 1, "uninitialized", 1
    except:
        return 1, "uninitialized", 1

async def setup(bot):
    """Setup function for Discord cog"""
    await bot.add_cog(DatabaseCog(bot))

# --- END OF FILE database.py ---