# --- START OF FILE dnd_cog.py ---
import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import random
import re
import sys
import time
import sqlite3
from typing import Dict, Tuple, List, Optional
from datetime import datetime
from enum import Enum

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from groq import Groq
from dotenv import load_dotenv

# Database imports
from database import (
    save_dnd_config, get_dnd_config, update_dnd_location, update_dnd_summary,
    add_dnd_history, get_dnd_history, update_dnd_rulebook, reset_campaign,
    save_active_party, update_character, get_character, 
    add_combatant, get_combat_order, clear_combat,
    get_dnd_campaign_data, advance_campaign_phase, 
    add_lore, get_lore, update_character_destiny, get_session_protagonist, 
    update_game_mode, add_monster_combatant, update_combatant_hp, 
    update_combatant_condition, remove_combatant, perform_long_rest_db, 
    update_quest_data, batch_update_destiny, get_combatant_conditions,
    get_target_language, DB_FILE,
    # Generational system functions
    save_session_mode, get_session_mode,
    save_legacy_data, get_legacy_data, save_soul_remnant, get_soul_remnants,
    mark_remnant_defeated, save_chronicles, get_chronicles, update_total_years
)

load_dotenv()
GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
AUDIO_PATH = "./audio/" 
FAST_MODEL = "llama-3.3-70b-versatile"
DICE_REGEX = re.compile(r"^\d+d\d+(\s*[+\-]\s*\d+)?$")

# --- OPTIMIZED CONSTANTS ---
LOCATION_THEMES = {
    "combat": 0xE74C3C, "forest": 0x2ECC71, "dungeon": 0x34495E,
    "tavern": 0xF1C40F, "boss": 0x000000, "city": 0x3498DB,
    "ocean": 0x3498DB, "desert": 0xE67E22, "volcano": 0xC0392B, "mountain": 0x95A5A6
}

RULES_2024 = "SYSTEM: D&D 5e (2024). Turn: 1 Action, 1 Bonus Action (Potion=BA). Heroic Inspiration=Reroll. Nat20=Inspiration. Surprise=Disadvantage (No Skip)."

# --- GENERATIONAL VOID CYCLE SYSTEM ---
# Dynamic time skip ranges for each phase transition
PHASE_TIME_SKIPS = {
    2: (20, 30),    # Phase 1→2: 20-30 years
    3: (500, 1000)  # Phase 2→3: 500-1000 years
}

# Biome configurations with phase-specific encounters
VOID_CYCLE_BIOMES = {
    "ocean": {
        "theme": "ocean", "color": 0x3498DB,
        "p1": {"mini": "Kraken", "boss": "Leviathan"},
        "p2": {"mini": "Jormungandr", "boss": "Cetus"},
        "p3": {"echo": "Echo Leviathan", "void": "The Abyssal Singularity"}
    },
    "volcano": {
        "theme": "volcano", "color": 0xC0392B,
        "p1": {"mini": "Fire Drake", "boss": "Red Dragon"},
        "p2": {"mini": "Nidhogg", "boss": "Magma Titan"},
        "p3": {"echo": "Echo Red Dragon", "void": "The Eternal Cinder"}
    },
    "desert": {
        "theme": "desert", "color": 0xE67E22,
        "p1": {"mini": "Sandworm", "boss": "Grootslag"},
        "p2": {"mini": "Behemoth", "boss": "Elder Sphinx"},
        "p3": {"echo": "Echo Grootslag", "void": "The Entropy Siphon"}
    },
    "forest": {
        "theme": "forest", "color": 0x2ECC71,
        "p1": {"mini": "Giant Spider", "boss": "Leshy"},
        "p2": {"mini": "Green Dragon", "boss": "World-Root"},
        "p3": {"echo": "Echo Leshy", "void": "The Withered Heart"}
    },
    "tundra": {
        "theme": "tundra", "color": 0x7FB3D5,
        "p1": {"mini": "Yeti", "boss": "Frost Giant"},
        "p2": {"mini": "Cryo-Hydra", "boss": "Rime-Worm"},
        "p3": {"echo": "Echo Frost Giant", "void": "The Absolute Zero"}
    },
    "sky": {
        "theme": "sky", "color": 0x85C1E9,
        "p1": {"mini": "Wyvern", "boss": "Storm Roc"},
        "p2": {"mini": "Quetzalcoatl", "boss": "Sky-Shatterer"},
        "p3": {"echo": "Echo Storm Roc", "void": "The Void Horizon"}
    }
}

# --- ARCHITECT vs SCRIBE MODE SYSTEM ---
class SessionModeManager:
    """Manages Architect (automatic) vs Scribe (manual) session modes"""
    
    ARCHITECT = "Architect"  # Vespera controls everything, auto tone shifting
    SCRIBE = "Scribe"        # Players have manual control over biome & tone
    
    @staticmethod
    def get_available_modes():
        return [SessionModeManager.ARCHITECT, SessionModeManager.SCRIBE]

# --- AUTOMATIC TONE SHIFTER (Architect Mode Only) ---
class AutomaticToneShifter:
    """Automatically shifts tone based on scene context in Architect Mode"""
    
    TONE_PROMPTS = {
        "Standard": "High-fantasy adventure with balanced humor and tension.",
        "Gritty": "Visceral, brutal combat. Focus on consequences and scars.",
        "Dramatic": "Epic, cinematic moments. High emotional stakes.",
        "Melancholy": "Poetic focus on decay, loss, and the passage of time.",
        "Mysterious": "Vague, unsettling. NPCs speak in riddles and omens.",
        "Humorous": "Light-hearted banter and clever wordplay."
    }
    
    @staticmethod
    def get_automatic_tone(scene_context: str) -> str:
        """Architect Mode: Automatically shifts tone based on scenario"""
        if "combat_start" in scene_context.lower():
            return "Gritty"
        elif "boss_defeat" in scene_context.lower():
            return "Dramatic"
        elif "time_skip" in scene_context.lower():
            return "Melancholy"
        elif "boss_appear" in scene_context.lower():
            return "Mysterious"
        elif "npc_meeting" in scene_context.lower():
            return "Humorous"
        return "Standard"
    
    @staticmethod
    def get_tone_context(tone: str) -> str:
        """Get the narrative context for a tone"""
        return AutomaticToneShifter.TONE_PROMPTS.get(tone, AutomaticToneShifter.TONE_PROMPTS["Standard"])

# --- DYNAMIC CHRONOS ENGINE (Randomized Time Skips) ---
class TimeSkipManager:
    """Manages randomized time skips between phases"""
    
    @staticmethod
    def generate_time_skip(target_phase: int) -> Tuple[int, str]:
        """Generate a random time skip for the target phase"""
        if target_phase not in PHASE_TIME_SKIPS:
            return 0, ""
        
        min_years, max_years = PHASE_TIME_SKIPS[target_phase]
        years = random.randint(min_years, max_years)
        
        if target_phase == 2:
            descriptors = [
                f"The world turns, and {years} years slip by like water.",
                f"Generations are born and age during {years} years of absence.",
                f"Civilizations shift and adapt across {years} long years.",
                f"Tales are written and forgotten in {years} years' time."
            ]
        else:  # Phase 3
            decades = years // 10
            centuries = years // 100
            descriptors = [
                f"Civilizations rise and fall across {years} years—{centuries} centuries of history.",
                f"The world forgets and remembers itself {centuries} times in {years} years.",
                f"Epochs pass in silence. {years} years have shattered the old world."
            ]
        
        flavor = random.choice(descriptors)
        return years, flavor
    
    @staticmethod
    def calculate_generations(years: int) -> Dict[str, int]:
        """Calculate generational impact of time skip"""
        generations = max(1, years // 25)
        dynasties = max(1, years // 100)
        
        return {
            "generations": generations,
            "dynasties": dynasties,
            "cultural_shifts": random.randint(2, 5) if years >= 500 else 1
        }

# --- CHARACTER LOCKING SYSTEM ---
class CharacterLockingSystem:
    """Lock/unlock characters based on campaign phase"""
    
    @staticmethod
    def is_character_locked_for_phase(character_data: Dict, target_phase: int) -> bool:
        """Check if character is locked out of current phase"""
        if target_phase < 3:
            return False  # Phase 1 & 2 have no locking
        
        char_generation = character_data.get('generation', 1)
        return char_generation == 1  # Phase 1 characters locked in Phase 3
    
    @staticmethod
    def create_soul_remnant_from_character(character_data: Dict, phase: int) -> Dict:
        """Convert a locked character into a soul remnant (mini-boss)"""
        return {
            "name": f"Soul Remnant ({character_data.get('name', 'Unknown')})",
            "hp": character_data.get('max_hp', 20),
            "max_hp": character_data.get('max_hp', 20),
            "ac": character_data.get('ac', 12),
            "signature_move": character_data.get('signature_move', 'Reality Tear'),
            "phase_created": phase,
            "glitched": True
        }

# --- LEVEL PROGRESSION SYSTEM ---
class LevelProgression:
    """Manage level progression across phases"""
    
    PHASE_LEVELS = {
        1: {"min": 1, "max": 20, "description": "Heroic (1-20)"},
        2: {"min": 21, "max": 30, "description": "Epic (21-30)"},
        3: {"min": 1, "max": 20, "description": "Legacy Reset (1-20)"}
    }
    
    @staticmethod
    def get_level_range(phase: int) -> Tuple[int, int]:
        """Get min/max level for phase"""
        levels = LevelProgression.PHASE_LEVELS.get(phase, LevelProgression.PHASE_LEVELS[1])
        return levels["min"], levels["max"]
    
    @staticmethod
    def generate_legacy_buff(legacy_data: Dict) -> str:
        """Generate legacy buff for descendant character"""
        destiny = legacy_data.get('destiny_roll', 0)
        
        if destiny >= 90:
            return random.choice([
                "Once per long rest: Automatically succeed on a saving throw",
                "Resistance to all damage from void creatures",
                "Advantage on all saving throws against fear"
            ])
        elif destiny >= 75:
            return random.choice([
                "+2 bonus to all saving throws",
                "Can add proficiency bonus to initiative rolls",
                "Advantage on Perception checks"
            ])
        elif destiny >= 50:
            return random.choice([
                "+1 bonus to all saving throws",
                "Resistance to psychic damage",
                "Advantage on checks related to ancestor's legacy"
            ])
        else:
            return random.choice([
                "Can't be surprised while conscious",
                "+1 bonus to attack rolls with ancestral weapons",
                "Once per long rest: Gain temp HP equal to level"
            ])

# --- RULEBOOK RAG SYSTEM ---
class RulebookRAG:
    """Efficient Rulebook Retrieval for 1GB RAM"""
    
    RULE_CACHE = {}
    CACHE_MAX_SIZE = 50
    
    @staticmethod
    def init_rulebook_table():
        """Initialize rulebook table in database"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS dnd_rulebook (
            keyword TEXT PRIMARY KEY,
            rule_text TEXT,
            rule_type TEXT,
            source TEXT
        )''')
        
        c.execute('''CREATE INDEX IF NOT EXISTS idx_rulebook_keyword 
                    ON dnd_rulebook(keyword)''')
        
        c.execute("SELECT COUNT(*) FROM dnd_rulebook")
        if c.fetchone()[0] == 0:
            # 2024 rules only
            core_rules = [
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
            
            c.executemany("INSERT INTO dnd_rulebook VALUES (?, ?, ?, ?)", core_rules)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def lookup_rule(keyword: str, limit: int = 3, require_precision: bool = False) -> List[Tuple[str, str]]:
        """Look up rules by keyword with enhanced precision filtering"""
        
        # Clean and enhance keyword for better matching
        keyword_clean = keyword.lower().strip()
        
        # Check cache first
        cache_key = f"{keyword_clean}_precise" if require_precision else keyword_clean
        if cache_key in RulebookRAG.RULE_CACHE:
            return RulebookRAG.RULE_CACHE[cache_key]
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Enhanced query with precision filtering
        if require_precision or "mechanics" in keyword_clean or "rule" in keyword_clean:
            # More precise search for mechanical terms
            if "mechanics" in keyword_clean:
                base_keyword = keyword_clean.replace(" mechanics", "").replace(" 5e", "")
                # Search for exact mechanical terms
                query = '''SELECT keyword, rule_text FROM dnd_rulebook 
                          WHERE (keyword LIKE ? OR rule_text LIKE ?)
                          AND (rule_type IN ('mechanic', 'action', 'spell', 'save'))
                          ORDER BY 
                            CASE WHEN keyword = ? THEN 1
                                 WHEN keyword LIKE ? THEN 2
                                 WHEN rule_text LIKE ? THEN 3
                                 ELSE 4
                            END
                          LIMIT ?'''
                
                c.execute(query, 
                         (f"%{base_keyword}%", f"%{base_keyword}%", 
                          base_keyword, f"{base_keyword}%", f"%{base_keyword}%", 
                          limit))
            else:
                # Regular but more precise search
                query = '''SELECT keyword, rule_text FROM dnd_rulebook 
                          WHERE keyword LIKE ? OR rule_text LIKE ?
                          ORDER BY 
                            CASE WHEN keyword = ? THEN 1
                                 WHEN keyword LIKE ? THEN 2
                                 WHEN rule_text LIKE ? THEN 3
                                 ELSE 4
                            END
                          LIMIT ?'''
                
                c.execute(query, 
                         (f"%{keyword_clean}%", f"%{keyword_clean}%", 
                          keyword_clean, f"{keyword_clean}%", f"%{keyword_clean}%", 
                          limit))
        else:
            # Original simpler search for non-mechanical terms
            c.execute('''SELECT keyword, rule_text FROM dnd_rulebook 
                        WHERE keyword LIKE ? OR rule_text LIKE ?
                        LIMIT ?''',
                     (f"%{keyword_clean}%", f"%{keyword_clean}%", limit))
        
        results = c.fetchall()
        conn.close()
        
        # Filter out low-confidence matches if precision required
        if require_precision and results:
            filtered_results = []
            for kw, rule_text in results:
                # Score match quality
                score = 0
                if keyword_clean in kw.lower():
                    score += 3
                if keyword_clean in rule_text.lower():
                    score += 2
                if "2024" in rule_text:
                    score += 1
                
                if score >= 2:  # Minimum confidence threshold
                    filtered_results.append((kw, rule_text))
            
            results = filtered_results[:limit]
        
        # Update cache
        if len(RulebookRAG.RULE_CACHE) >= RulebookRAG.CACHE_MAX_SIZE:
            RulebookRAG.RULE_CACHE.pop(next(iter(RulebookRAG.RULE_CACHE)))
        
        RulebookRAG.RULE_CACHE[cache_key] = results
        
        return results
    
    @staticmethod
    def add_rule(keyword: str, rule_text: str, rule_type: str = "custom", source: str = "DM"):
        """Add a custom rule to the rulebook"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute("INSERT OR REPLACE INTO dnd_rulebook VALUES (?, ?, ?, ?)",
                 (keyword.lower(), rule_text, rule_type, source))
        
        conn.commit()
        conn.close()
        
        RulebookRAG.RULE_CACHE[keyword.lower()] = [(keyword, rule_text)]

# --- LOCAL SRD LIBRARY ---
class SRDLibrary:
    """Lightweight SRD library using JSON files"""
    
    SRD_CACHE = {}
    
    @staticmethod
    def load_srd_data(category: str) -> dict:
        """Load SRD data from JSON file"""
        if category in SRDLibrary.SRD_CACHE:
            return SRDLibrary.SRD_CACHE[category]
        
        srd_path = f"./srd/{category}.json"
        if os.path.exists(srd_path):
            try:
                with open(srd_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    SRDLibrary.SRD_CACHE[category] = data
                    return data
            except:
                pass
        
        fallback = {
            "spells": {
                "fireball": {
                    "name": "Fireball",
                    "level": 3,
                    "school": "Evocation",
                    "casting_time": "1 action",
                    "range": "150 feet",
                    "components": "V, S, M",
                    "duration": "Instantaneous",
                    "description": "A bright streak flashes to a point within range, exploding with flame (8d6 fire damage)."
                }
            }
        }
        return fallback.get(category, {})
    
    @staticmethod
    def search_srd(category: str, query: str, limit: int = 5) -> list:
        """Search SRD data by query"""
        data = SRDLibrary.load_srd_data(category)
        query = query.lower()
        results = []
        
        for key, item in data.items():
            if query in key.lower() or query in item.get('name', '').lower():
                results.append(item)
                if len(results) >= limit:
                    break
        
        return results

# --- HISTORY MANAGER ---
class HistoryManager:
    """Efficient history management with summarization"""
    
    @staticmethod
    async def summarize_history(guild_id: int, thread_id: int, force: bool = False) -> Optional[str]:
        """Summarize old history entries to save tokens"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM dnd_history WHERE thread_id=?", (str(thread_id),))
        count = c.fetchone()[0]
        
        if count < 20 and not force:
            conn.close()
            return None
        
        c.execute('''SELECT role, content FROM dnd_history 
                    WHERE thread_id=? 
                    ORDER BY timestamp ASC LIMIT 15''', 
                 (str(thread_id),))
        old_entries = c.fetchall()
        
        if not old_entries:
            conn.close()
            return None
        
        history_text = "\n".join([f"{role}: {content[:100]}" for role, content in old_entries])
        
        prompt = f"""Summarize these D&D session events into 2-3 sentences:
        
        {history_text}
        
        Summary:"""
        
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: GROQ_CLIENT.chat.completions.create(
                        model=FAST_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=150
                    )
                ),
                timeout=10.0
            )
            
            summary = response.choices[0].message.content.strip()
            
            c.execute('''DELETE FROM dnd_history 
                        WHERE thread_id=? AND timestamp IN (
                            SELECT timestamp FROM dnd_history 
                            WHERE thread_id=? 
                            ORDER BY timestamp ASC LIMIT 15
                        )''', (str(thread_id), str(thread_id)))
            
            c.execute('''INSERT INTO dnd_history (thread_id, role, content, timestamp)
                        VALUES (?, ?, ?, ?)''',
                     (str(thread_id), "SUMMARY", summary, time.time()))
            
            conn.commit()
            conn.close()
            
            return summary
            
        except Exception as e:
            conn.close()
            print(f"[History] Summarization failed: {e}")
            return None
    
    @staticmethod
    def get_optimized_history(thread_id: int, limit: int = 8) -> List[Tuple[str, str]]:
        """Get history with efficient windowing"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''SELECT role, content FROM dnd_history 
                    WHERE thread_id=? 
                    ORDER BY timestamp DESC LIMIT ?''',
                 (str(thread_id), limit))
        
        results = c.fetchall()
        conn.close()
        
        return results[::-1]

# --- COMPACT COMBAT TRACKER ---
class CombatTracker:
    """Optimized combat tracker with reference numbers"""
    
    @staticmethod
    def get_combat_with_refs(thread_id: int) -> List[Dict]:
        """Get combatants with reference numbers"""
        combatants = get_combat_order(thread_id)
        result = []
        
        for idx, (uid, name, init, curr_hp, max_hp, is_monster, conditions) in enumerate(combatants, 1):
            result.append({
                "ref": idx,
                "id": uid,
                "name": name,
                "init": init,
                "hp": curr_hp,
                "max_hp": max_hp,
                "is_monster": is_monster,
                "conditions": conditions,
                "display": f"[{idx}] {name} ({curr_hp}/{max_hp})"
            })
        
        return result
    
    @staticmethod
    def apply_damage_by_ref(thread_id: int, ref: int, damage: int) -> Optional[Dict]:
        """Apply damage using reference number"""
        combatants = CombatTracker.get_combat_with_refs(thread_id)
        
        for combatant in combatants:
            if combatant["ref"] == ref:
                new_hp = update_combatant_hp(thread_id, combatant["id"], -damage)
                
                if new_hp <= 0 and combatant["is_monster"] == 1:
                    remove_combatant(thread_id, combatant["id"])
                    combatant["status"] = "defeated"
                else:
                    combatant["hp"] = new_hp
                    combatant["status"] = "damaged"
                
                return combatant
        
        return None
    
    @staticmethod
    def get_combat_summary(thread_id: int) -> str:
        """Get compact combat summary"""
        combatants = CombatTracker.get_combat_with_refs(thread_id)
        
        if not combatants:
            return "No active combat."
        
        players = [c for c in combatants if c["is_monster"] == 0]
        monsters = [c for c in combatants if c["is_monster"] == 1]
        npcs = [c for c in combatants if c["is_monster"] == 2]
        
        lines = []
        
        if players:
            lines.append("**Players:**")
            for c in players:
                hp_emoji = "💚" if c["hp"] > c["max_hp"] * 0.5 else "🧡" if c["hp"] > c["max_hp"] * 0.1 else "💔"
                lines.append(f"  {hp_emoji} {c['name']}: {c['hp']}/{c['max_hp']}")
        
        if monsters:
            lines.append("**Enemies:**")
            for c in monsters[:5]:
                lines.append(f"  [{c['ref']}] {c['name']}: {c['hp']}/{c['max_hp']}")
            if len(monsters) > 5:
                lines.append(f"  ...and {len(monsters) - 5} more")
        
        if npcs:
            lines.append("**Allies:**")
            for c in npcs[:3]:
                lines.append(f"  {c['name']}: {c['hp']}/{c['max_hp']}")
        
        return "\n".join(lines)

# --- SESSION SCRIBE ---
class SessionScribe:
    """Generate session summaries"""
    
    @staticmethod
    def generate_session_embed(guild_id: int, thread_id: int, session_title: str = "Session Report") -> discord.Embed:
        """Generate a session summary embed"""
        config = get_dnd_config(guild_id)
        if not config:
            return None
        
        history = get_dnd_history(thread_id, limit=15)
        
        player_actions = []
        dm_narration = []
        
        for role, content in history:
            if role == "DM":
                dm_narration.append(content[:100])
            elif role != "SUMMARY":
                player_actions.append(f"{role}: {content[:50]}")
        
        embed = discord.Embed(
            title=f"📝 {session_title}",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        
        quest_name = "Adventure"
        if config[10]:
            try:
                quest_data = json.loads(config[10])
                quest_name = quest_data.get('name', quest_name)
            except:
                pass
        
        embed.add_field(name="Quest", value=quest_name, inline=True)
        embed.add_field(name="Location", value=config[1] or "Unknown", inline=True)
        
        if player_actions:
            actions_text = "\n".join(player_actions[:5])
            if len(player_actions) > 5:
                actions_text += f"\n...and {len(player_actions) - 5} more actions"
            embed.add_field(name="Recent Actions", value=actions_text, inline=False)
        
        if dm_narration:
            narration_text = "... ".join(dm_narration[-3:])[:300]
            embed.add_field(name="Story Progress", value=narration_text + "...", inline=False)
        
        protagonist, score = get_session_protagonist(guild_id)
        if protagonist:
            embed.add_field(name="Protagonist", value=f"{protagonist} (Destiny: {score})", inline=True)
        
        embed.set_footer(text="Vespera Chronicles • Session recorded")
        
        return embed

# --- DESTINY MANAGER ---
class DestinyManager:
    """Manage destiny milestones and triggers"""
    
    DESTINY_MILESTONES = {
        25: "Minor milestone: Character gains a clue or small advantage.",
        50: "Major milestone: Character unlocks a special ability or learns important lore.",
        75: "Critical milestone: Character's personal quest advances significantly.",
        90: "Legendary milestone: Character becomes central to the campaign's climax."
    }
    
    @staticmethod
    def check_destiny_triggers(guild_id: int, user_id: int) -> List[str]:
        """Check if destiny score triggers any milestones"""
        char = get_character(user_id, guild_id)
        if not char or 'destiny_roll' not in char:
            return []
        
        destiny_score = char['destiny_roll']
        triggers = []
        
        for threshold, message in DestinyManager.DESTINY_MILESTONES.items():
            if destiny_score >= threshold:
                milestone_key = f"milestone_{threshold}"
                if milestone_key not in char.get('milestones', []):
                    triggers.append(message)
                    
                    if 'milestones' not in char:
                        char['milestones'] = []
                    char['milestones'].append(milestone_key)
                    update_character(user_id, guild_id, char)
        
        return triggers

# --- DM OVERSIGHT ---
class DMOversight:
    """Ghost DM mode for suggesting outcomes"""
    
    @staticmethod
    async def suggest_outcome(guild_id: int, player_action: str, context: str) -> Dict:
        """Suggest a DM response before posting"""
        prompt = f"""As a DM assistant, suggest 3 possible outcomes for this player action:
        
        Context: {context[:200]}
        Action: {player_action}
        
        Provide 3 options: 
        1. A favorable outcome
        2. A challenging outcome
        3. A dramatic twist
        
        Return as JSON: {{"options": ["option1", "option2", "option3"], "recommended": "index"}}"""
        
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: GROQ_CLIENT.chat.completions.create(
                        model=FAST_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=300,
                        response_format={"type": "json_object"}
                    )
                ),
                timeout=15.0
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"[DM Oversight] Error: {e}")
            return {
                "options": [
                    "The action succeeds as expected.",
                    "The action succeeds with a complication.",
                    "The action fails but reveals something important."
                ],
                "recommended": 0
            }

# --- HELPER FUNCTIONS ---
async def validate_dnd_access(i):
    """Optimized validation function"""
    try:
        if i.user.guild_permissions.manage_guild:
            return True
        s = get_dnd_config(i.guild.id)
        if not s:
            return False
        role_id = s[4] if len(s) > 4 else None
        if not role_id or role_id == "None":
            return True
        role = i.guild.get_role(int(role_id))
        return True if not role or role in i.user.roles else False
    except Exception:
        return False

def is_dnd_player():
    async def predicate(interaction):
        return await validate_dnd_access(interaction)
    return app_commands.check(predicate)

def get_hp_emoji(curr, max_hp):
    """Optimized HP emoji function"""
    if max_hp <= 0:
        return "⚪"
    ratio = curr / max_hp
    if ratio > 0.5:
        return "💚"
    elif ratio > 0.1:
        return "🧡"
    return "💔"

# --- PRE-COMPUTATION ENGINE ---
class PrecomputationEngine:
    """Pre-compute dice rolls and outcomes to prevent AI hallucination"""
    
    @staticmethod
    def roll_dice(dice_string: str) -> tuple:
        """Parse dice strings like '2d6+3' and return (total, individual_rolls, modifier)"""
        if not dice_string or not isinstance(dice_string, str):
            return (0, [], 0)
        
        # Remove whitespace
        dice_string = dice_string.lower().replace(" ", "")
        
        try:
            # Check for dice pattern (e.g., 2d6+3)
            dice_match = re.match(r"^(\d+)d(\d+)([+\-]\d+)?$", dice_string)
            if dice_match:
                num_dice = int(dice_match.group(1))
                dice_type = int(dice_match.group(2))
                modifier = int(dice_match.group(3) or 0)
                
                # Roll individual dice
                rolls = [random.randint(1, dice_type) for _ in range(num_dice)]
                total = sum(rolls) + modifier
                
                return (total, rolls, modifier)
            
            # Check for single die (e.g., d20+5)
            single_match = re.match(r"^d(\d+)([+\-]\d+)?$", dice_string)
            if single_match:
                dice_type = int(single_match.group(1))
                modifier = int(single_match.group(2) or 0)
                roll = random.randint(1, dice_type)
                return (roll + modifier, [roll], modifier)
                
        except Exception:
            pass
        
        return (0, [], 0)
    
    @staticmethod
    def compute_attack_result(attack_bonus: int, target_ac: int) -> dict:
        """Pre-compute attack roll results"""
        roll = random.randint(1, 20)
        natural_roll = roll
        total = roll + attack_bonus
        
        if natural_roll == 20:
            status = "CRITICAL_HIT"
        elif natural_roll == 1:
            status = "CRITICAL_MISS"
        elif total >= target_ac:
            status = "HIT"
        else:
            status = "MISS"
        
        return {
            "natural_roll": natural_roll,
            "total_roll": total,
            "status": status,
            "attack_bonus": attack_bonus,
            "target_ac": target_ac
        }
    
    @staticmethod
    def compute_damage(dice_string: str, is_crit: bool = False) -> dict:
        """Pre-compute damage rolls"""
        if is_crit:
            # For crits, double the dice (but not the modifier)
            if "d" in dice_string:
                # Parse and double dice count
                parts = dice_string.split("d")
                if len(parts) == 2:
                    num_dice = int(parts[0]) * 2 if parts[0] else 2
                    rest = parts[1]
                    # Find modifier
                    if "+" in rest or "-" in rest:
                        for op in ["+", "-"]:
                            if op in rest:
                                dice_part, mod_part = rest.split(op)
                                dice_string = f"{num_dice}d{dice_part}{op}{mod_part}"
                                break
                    else:
                        dice_string = f"{num_dice}d{rest}"
        
        total, rolls, modifier = PrecomputationEngine.roll_dice(dice_string)
        
        return {
            "total": total,
            "individual_rolls": rolls,
            "modifier": modifier,
            "dice_string": dice_string,
            "is_crit": is_crit
        }
    
    @staticmethod
    def compute_saving_throw(dc: int, save_bonus: int, advantage: bool = False, disadvantage: bool = False) -> dict:
        """Pre-compute saving throw results"""
        if advantage and disadvantage:
            advantage = disadvantage = False
        
        if advantage:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            natural_roll = max(roll1, roll2)
        elif disadvantage:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            natural_roll = min(roll1, roll2)
        else:
            natural_roll = random.randint(1, 20)
        
        total = natural_roll + save_bonus
        success = total >= dc
        
        return {
            "natural_roll": natural_roll,
            "total": total,
            "dc": dc,
            "save_bonus": save_bonus,
            "success": success,
            "margin": abs(total - dc)
        }

def generate_truth_block(action: str, character_data: dict = None, target_data: dict = None) -> str:
    """
    Generate a truth block for pre-computed mechanics to prevent hallucinations.
    
    Args:
        action: Player's action description
        character_data: Character stats (optional)
        target_data: Target stats (optional)
    
    Returns:
        Truth block string to prepend to AI prompt
    """
    truth_lines = []
    
    # Add TRUTH BLOCK header
    truth_lines.append("=" * 60)
    truth_lines.append("GAME ENGINE TRUTH BLOCK - USE THESE EXACT VALUES")
    truth_lines.append("=" * 60)
    
    # Parse action for common mechanics
    action_lower = action.lower()
    
    # Check for attack rolls
    attack_keywords = ["attack", "hit", "strike", "smash", "slash", "shoot"]
    if any(keyword in action_lower for keyword in attack_keywords):
        # Pre-compute attack
        attack_bonus = character_data.get('attack_bonus', 0) if character_data else 0
        target_ac = target_data.get('ac', 15) if target_data else 15
        
        attack_result = PrecomputationEngine.compute_attack_result(attack_bonus, target_ac)
        
        truth_lines.append(f"[ATTACK RESULT]")
        truth_lines.append(f"Natural Roll: {attack_result['natural_roll']}")
        truth_lines.append(f"Total (with +{attack_bonus}): {attack_result['total_roll']}")
        truth_lines.append(f"Target AC: {target_ac}")
        truth_lines.append(f"Outcome: {attack_result['status']}")
        
        # Pre-compute damage if hit/crit
        if attack_result['status'] in ["HIT", "CRITICAL_HIT"]:
            damage_dice = character_data.get('damage_dice', '1d8') if character_data else '1d8'
            damage_bonus = character_data.get('damage_bonus', 0) if character_data else 0
            is_crit = attack_result['status'] == "CRITICAL_HIT"
            
            damage_result = PrecomputationEngine.compute_damage(f"{damage_dice}+{damage_bonus}", is_crit)
            
            truth_lines.append(f"[DAMAGE RESULT]")
            truth_lines.append(f"Dice: {damage_result['dice_string']}")
            truth_lines.append(f"Individual Rolls: {damage_result['individual_rolls']}")
            truth_lines.append(f"Modifier: {damage_result['modifier']}")
            truth_lines.append(f"Total Damage: {damage_result['total']}")
    
    # Check for ability checks/saving throws
    check_keywords = ["check", "save", "save against", "resist", "test"]
    for keyword in check_keywords:
        if keyword in action_lower:
            # Extract ability if mentioned
            abilities = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
            ability_found = None
            for ability in abilities:
                if ability in action_lower:
                    ability_found = ability
                    break
            
            dc = 15  # Default DC
            save_bonus = character_data.get(f'{ability_found}_mod', 0) if character_data and ability_found else 0
            
            save_result = PrecomputationEngine.compute_saving_throw(dc, save_bonus)
            
            truth_lines.append(f"[SAVING THROW RESULT]")
            truth_lines.append(f"Ability: {ability_found or 'Unknown'}")
            truth_lines.append(f"Natural Roll: {save_result['natural_roll']}")
            truth_lines.append(f"Total (with +{save_bonus}): {save_result['total']}")
            truth_lines.append(f"DC: {dc}")
            truth_lines.append(f"Success: {save_result['success']}")
            break
    
    # Check for spell casting
    spell_keywords = ["cast", "spell", "magic", "incantation"]
    if any(keyword in action_lower for keyword in spell_keywords):
        # Extract spell level if mentioned
        for level in range(1, 10):
            if f"level {level}" in action_lower or f"{level}st" in action_lower or f"{level}nd" in action_lower or f"{level}rd" in action_lower or f"{level}th" in action_lower:
                truth_lines.append(f"[SPELL CASTING]")
                truth_lines.append(f"Spell Level: {level}")
                truth_lines.append(f"Concentration Required: {'Yes' if level >= 1 else 'No'}")
                break
    
    # Add HP status
    if character_data:
        truth_lines.append(f"[CHARACTER STATUS]")
        truth_lines.append(f"Current HP: {character_data.get('hp', '?')}/{character_data.get('max_hp', '?')}")
        truth_lines.append(f"AC: {character_data.get('ac', '?')}")
        if character_data.get('conditions'):
            truth_lines.append(f"Conditions: {character_data.get('conditions')}")
    
    # Add target status
    if target_data:
        truth_lines.append(f"[TARGET STATUS]")
        truth_lines.append(f"Target Name: {target_data.get('name', 'Unknown')}")
        truth_lines.append(f"Target HP: {target_data.get('hp', '?')}/{target_data.get('max_hp', '?')}")
        truth_lines.append(f"Target AC: {target_data.get('ac', '?')}")
    
    truth_lines.append("=" * 60)
    truth_lines.append("END TRUTH BLOCK - DO NOT DEVIATE FROM THESE VALUES")
    truth_lines.append("=" * 60)
    truth_lines.append("")
    
    return "\n".join(truth_lines)

# --- OPTIMIZED NPC GENERATOR ---
class NPCNameGenerator:
    """Optimized name generator"""
    
    SIMPLE_THEMES = {
        "ocean": ["Aqua", "Mar", "Tidal", "Coral", "Wave", "Deep", "Salt"],
        "volcano": ["Ignis", "Pyro", "Magma", "Ash", "Flame", "Ember"],
        "desert": ["Sand", "Dune", "Sun", "Oasis", "Mirage", "Dust"]
    }
    
    SIMPLE_TITLES = [
        "the Brave", "the Wise", "the Fierce", "the Cunning", 
        "the Ancient", "the Young", "the Scarred", "the Silent"
    ]
    
    @staticmethod
    def generate_name(theme: str, npc_type: str = "guardian") -> str:
        """Generate simple, thematic NPC names"""
        themes = NPCNameGenerator.SIMPLE_THEMES.get(theme, NPCNameGenerator.SIMPLE_THEMES["ocean"])
        prefix = random.choice(themes)
        
        if npc_type == "boss":
            suffixes = ["lord", "king", "tyrant", "heart", "wrath"]
            suffix = random.choice(suffixes)
            return f"{prefix}{suffix.capitalize()}"
        elif npc_type == "miniboss":
            descriptors = ["Hunter", "Warden", "Sentinel", "Champion"]
            descriptor = random.choice(descriptors)
            return f"{prefix}{descriptor}"
        else:
            guardian_types = ["Valiant", "Stalwart", "Vigilant", "Dauntless"]
            guardian_type = random.choice(guardian_types)
            return f"{guardian_type} {prefix}warden"

# --- CONQUEST PATHS ---
CONQUEST_PATHS = {
    "ocean": {
        "p1": {"name": "Leviathan Conquest", "mini": "Kraken", "boss": "Leviathan", "theme": "ocean"},
        "p2": {"name": "Abyssal Return", "mini": "Jormungandr", "boss": "Tiamat", "theme": "ocean"}
    },
    "volcano": {
        "p1": {"name": "Red Dragon Conquest", "mini": "Griffith", "boss": "Red Dragon", "theme": "volcano"},
        "p2": {"name": "Infernal Legacy", "mini": "Nidhogg", "boss": "Apep", "theme": "volcano"}
    },
    "desert": {
        "p1": {"name": "Grootslag Conquest", "mini": "Sandworm", "boss": "Grootslag", "theme": "desert"},
        "p2": {"name": "Sands of Time", "mini": "Hydra", "boss": "Fenrir", "theme": "desert"}
    }
}

# --- UI VIEWS ---
class CharacterSelectionModal(discord.ui.Modal):
    """Modal for selecting character after launch - appears to joined players only"""
    def __init__(self, bot_cog, guild_id: int, joined_users: list):
        super().__init__(title="Select Your Character")
        self.bot_cog = bot_cog
        self.guild_id = guild_id
        self.joined_users = joined_users
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle character confirmation"""
        if interaction.user.id not in self.joined_users:
            await interaction.response.send_message("❌ You didn't join the session!", ephemeral=True)
            return
        
        char = get_character(interaction.user.id, self.guild_id)
        if not char or not char.get('name'):
            await interaction.response.send_message("❌ No character imported. Use /import_character first.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"✅ <@{interaction.user.id}> selected **{char.get('name')}**!",
            ephemeral=False
        )


class CharacterSelectionView(discord.ui.View):
    """
    View for character selection - appears after launch to prompt character picks.
    Players select their characters, then press Ready when all have selected.
    Ready button only activates when all joined players (non-NPCs) have selected characters.
    """
    def __init__(self, bot_cog, guild_id: int, joined_users: list, phase: int = 1, rulebook: str = "5e 2024"):
        super().__init__(timeout=300)
        self.bot_cog = bot_cog  # Reference to main cog for launching game logic
        self.guild_id = guild_id  # Guild/server identifier
        self.joined_users = joined_users  # List of user IDs who joined the session
        self.selected_characters = {}  # Dict to track {user_id: character_name} selections
        self.phase = phase  # Current campaign phase (for prologue context)
        self.rulebook = rulebook  # Rules system being used
    
    @discord.ui.button(label="Select Character", style=discord.ButtonStyle.primary)
    async def select_char_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button that lets each player select their imported character"""
        # Verify user joined the session
        if interaction.user.id not in self.joined_users:
            await interaction.response.send_message("❌ You didn't join this session!", ephemeral=True)
            return
        
        # Get user's previously imported character from database
        char = get_character(interaction.user.id, self.guild_id)
        if not char or not char.get('name'):
            await interaction.response.send_message("❌ You haven't imported a character yet. Use `/import_character` first.", ephemeral=True)
            return
        
        # Store this user's character selection in our tracking dict
        self.selected_characters[interaction.user.id] = char.get('name')
        
        # Send confirmation embed to the player (ephemeral = only they see it)
        embed = discord.Embed(
            title="✅ Character Selected",
            description=f"<@{interaction.user.id}> → **{char.get('name')}**",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success)
    async def ready_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Ready button - triggers ONLY when pressed AND all players have selected characters.
        This is where the prologue gets triggered and the game officially begins.
        """
        # Verify user joined the session
        if interaction.user.id not in self.joined_users:
            await interaction.response.send_message("❌ You didn't join this session!", ephemeral=True)
            return
        
        # Verify user has selected a character
        if interaction.user.id not in self.selected_characters:
            await interaction.response.send_message("❌ Select a character first!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Count how many players have selected (exclude NPCs like "npc_guardian_0")
        ready_count = len(self.selected_characters)
        total_players = len([u for u in self.joined_users if not str(u).startswith("npc_")])
        
        # Check if all players are ready
        if ready_count >= total_players:
            # All players ready! Prepare the ready confirmation
            ready_embed = discord.Embed(
                title="🎮 All Players Ready!",
                description=f"{ready_count}/{total_players} players have selected characters.\n\n**Initiating Prologue...**",
                color=0x3498DB
            )
            await interaction.followup.send(embed=ready_embed)
            
            # PROLOGUE TRIGGER: Now that all players are ready, launch the game and prologue
            # This replaces the old launch_btn prologue trigger
            await self.bot_cog.launch_game_logic(interaction, self.phase, self.rulebook)
            
            # Disable all buttons on this view to prevent further interactions
            for item in self.children:
                item.disabled = True
            try:
                await interaction.message.edit(view=self)
            except:
                pass
        else:
            # Not all players ready yet - show waiting message
            remaining = total_players - ready_count
            await interaction.followup.send(
                f"⏳ **Waiting for {remaining} more player(s)** to select their characters before you can press Ready.",
                ephemeral=True
            )



class SessionLobbyView(discord.ui.View):
    """
    Main session lobby view for D&D sessions.
    - Row 0: Join/Leave/Continue buttons for party management
    - Row 1: Launch Session and Reset Campaign buttons
    
    Character selection moved to AFTER launch (in CharacterSelectionView).
    Prologue now triggered when all players press Ready in character selection.
    
    NOTE: Mode/Tone/Biome selection moved to separate modal/view to avoid layout issues.
    """
    
    def __init__(self, bot_cog, interaction, phase, has_save, initial_party=None, quest_title="Adventure", legends=None):
        super().__init__(timeout=300)
        self.bot_cog = bot_cog  # Reference to main cog
        self.host_id = interaction.user.id  # Host who started the session
        self.phase = phase  # Current campaign phase (1, 2, or 3)
        self.has_save = has_save  # Whether there's a saved session to continue
        self.joined_users = list(initial_party) if initial_party else [interaction.user.id]  # List of user IDs in party
        self.quest_title = quest_title  # Title of the current quest/campaign
        self.legends = legends or []  # Survivors from Phase 1 (for Phase 2+ continuation)
        self.rulebook = "5e 2024"  # Rules system
        self.guild_id = interaction.guild.id  # Guild identifier
        
        # Initialize session mode settings (will be used if Scribe mode selected)
        self.session_mode = "Architect"  # Default to Architect mode
        self.selected_tone = "Standard"  # Default tone
        self.selected_biome = "forest"  # Default biome
    
    def update_embed(self):
        """Create and return the lobby status embed showing party composition and settings"""
        # Build party list description
        description = f"**{self.quest_title}**\nRules: {self.rulebook}\n\n**Party ({len(self.joined_users)}/12):**\n"
        
        # List all joined players (exclude NPCs)
        for user_id in self.joined_users:
            if not str(user_id).startswith("npc_"):
                description += f"• ⚔️ <@{user_id}>\n"
            else:
                # Show NPC names if they've been saved
                char = get_character(user_id, self.guild_id)
                if char:
                    description += f"• 🛡️ {char.get('name', 'Guardian')}\n"
        
        # Add legend info if continuing from Phase 1
        if self.phase > 1 and self.legends:
            description += f"\n**Legends (Survivors):** {len(self.legends)}"
        
        # Create the main embed with current settings
        embed = discord.Embed(
            title="🎲 D&D Session Lobby",
            description=description,
            color=0x3498db
        )
        
        # Show current session settings
        embed.add_field(
            name="⚙️ Session Settings",
            value=f"Mode: **{self.session_mode}**\n" +
                  (f"Tone: **{self.selected_tone}**\n" if self.session_mode == "Scribe" else "") +
                  (f"Biome: **{self.selected_biome.title()}**" if self.session_mode == "Scribe" else ""),
            inline=False
        )
        
        embed.set_footer(text="Vespera // The stage is set")
        return embed
    
    # ========== ROW 0: PARTY MANAGEMENT BUTTONS ==========
    
    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, row=0)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Join button - allows a player to join the session.
        In Phase 2+, only survivors (legends) from Phase 1 can join.
        Disabled if game is already in progress (has_save = True).
        """
        # ===== STATE VALIDATION =====
        # Check if button should be enabled
        if self.has_save:
            await interaction.response.send_message(
                "⛔ **Cannot join:** A game is already in progress. Use the **Continue** button instead, or **Reset Campaign** to start fresh.",
                ephemeral=True
            )
            return
        
        if not await validate_dnd_access(interaction):
            return
        
        # ===== PHASE RESTRICTIONS =====
        # Check phase restrictions: only legends can join in Phase 2+
        if self.phase > 1:
            legend_ids = [l.get('id') for l in self.legends if isinstance(l, dict) and not str(l.get('id', '')).startswith("npc_")]
            if interaction.user.id not in legend_ids:
                await interaction.response.send_message(
                    "⛔ **Cannot join Phase 2+:** Only survivors from Phase 1 can participate in future phases.\n"
                    "Your character did not survive the previous campaign.",
                    ephemeral=True
                )
                return
        
        # ===== ADD PLAYER TO PARTY =====
        # Add player to party if not already joined
        if interaction.user.id not in self.joined_users:
            self.joined_users.append(interaction.user.id)
            await interaction.response.edit_message(embed=self.update_embed(), view=self)
        else:
            await interaction.response.send_message("✅ You're already in the party!", ephemeral=True)
    
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, row=0)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Leave button - removes a player from the session.
        Disabled if game is already in progress (has_save = True).
        """
        # ===== STATE VALIDATION =====
        # Check if button should be enabled
        if self.has_save:
            await interaction.response.send_message(
                "⛔ **Cannot leave:** A game is already in progress. Use **Reset Campaign** if you want to abandon the session.",
                ephemeral=True
            )
            return
        
        # ===== REMOVE PLAYER FROM PARTY =====
        if interaction.user.id in self.joined_users:
            # Prevent host from leaving if they're the only one (avoid empty party)
            if interaction.user.id == self.host_id and len(self.joined_users) == 1:
                await interaction.response.send_message(
                    "⛔ **Cannot leave:** As the host, you cannot leave if you're the only party member. "
                    "Add other players first, or disband the session.",
                    ephemeral=True
                )
                return
            
            self.joined_users.remove(interaction.user.id)
            await interaction.response.edit_message(embed=self.update_embed(), view=self)
        else:
            await interaction.response.send_message("ℹ️ You're not in the party", ephemeral=True)
    
    @discord.ui.button(label="Continue", style=discord.ButtonStyle.blurple, row=0)
    async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Continue button - resumes a saved game session.
        Only appears and works if there's a previously saved session.
        Only host can click this button.
        
        ===== DEFENSIVE STATE VALIDATION =====
        - Checks if a save exists (if not, rejects)
        - Verifies only host can continue (prevents player confusion)
        - Provides helpful error messages for edge cases
        """
        # ===== DISABLE BUTTON TO PREVENT DOUBLE-CLICKS =====
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        # ===== VALIDATION: SAVE EXISTS =====
        # Verify a save truly exists before attempting to continue
        config = get_dnd_config(interaction.guild.id)
        if not config or not config[2] or config[2] == "New Campaign Started.":
            await interaction.response.send_message(
                "⛔ **No save to continue:** There is no saved game progress to resume.\n"
                "Use **Launch Session** to start a new campaign.",
                ephemeral=True
            )
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        # ===== HOST-ONLY PROTECTION =====
        # Only the session host can continue to prevent conflicts
        if interaction.user.id != self.host_id:
            await interaction.response.send_message(
                "⛔ **Only the host can continue the session.** "
                f"Ask <@{self.host_id}> to continue.",
                ephemeral=True
            )
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        # ===== VALIDATE ACTIVE PARTY =====
        # Ensure there are players to continue with
        if len(self.joined_users) == 0:
            await interaction.response.send_message(
                "⛔ **Cannot continue:** No players in the party.\n"
                "Use **Reset Campaign** to clean up and start fresh with /start_session.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Save current party and attempt to sync quest location before launching
            save_active_party(interaction.guild.id, self.joined_users)

            # CRITICAL: Ensure quest data location matches config to avoid hallucinations
            try:
                cfg = get_dnd_config(interaction.guild.id)
                if cfg and cfg[10]:
                    try:
                        qd = json.loads(cfg[10]) if isinstance(cfg[10], str) else cfg[10]
                        if isinstance(qd, dict):
                            quest_theme = qd.get('theme', qd.get('path_key', None))
                            current_loc = cfg[1] if cfg[1] else None
                            if quest_theme and current_loc and quest_theme.lower() != str(current_loc).lower():
                                # Update stored location to match quest theme
                                try:
                                    update_dnd_location(interaction.guild.id, quest_theme)
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

            # ===== CRITICAL FIX: Pass is_continue=True to skip prologue =====
            await self.bot_cog.launch_game_logic(interaction, self.phase, self.rulebook, is_continue=True)
            
            # Disable all buttons after continuing (gracefully handle errors)
            try:
                for child in self.children:
                    child.disabled = True
                await interaction.message.edit(view=self)
            except (discord.NotFound, Exception):
                # Message was deleted or other error, that's OK
                pass
        except Exception as e:
            # Error recovery: inform user and suggest alternatives
            error_msg = str(e)[:100] if str(e) else "Unknown error"
            await interaction.followup.send(
                f"⚠️ **Error resuming game:** {error_msg}\n"
                "Try **Reset Campaign** and start a new session instead.",
                ephemeral=True
            )
    
    # ========== ROW 1: SETTINGS & LAUNCH BUTTONS ==========
    
    @discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.blurple, row=1)
    async def settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Settings button - opens mode/tone/biome selector modal for Scribe mode.
        Host only.
        """
        # ===== DISABLE BUTTON TO PREVENT DOUBLE-CLICKS =====
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        # ===== STATE VALIDATION =====
        # Prevent changing settings during active game
        config = get_dnd_config(interaction.guild.id)
        if config and config[2] and config[2] != "New Campaign Started.":
            await interaction.response.send_message(
                "⛔ **Cannot change settings:** A game is already in progress.\n"
                "Settings are locked during an active session. Use **Reset Campaign** to abandon this session and start fresh.",
                ephemeral=True
            )
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("⛔ Only the host can change settings.", ephemeral=True)
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        # ===== SHOW SETTINGS MENU =====
        # Show a select menu for mode selection
        view = discord.ui.View()
        
        mode_select = discord.ui.Select(
            placeholder="Select Game Mode...",
            options=[
                discord.SelectOption(label="Architect Mode", value="architect", description="Vespera controls tone"),
                discord.SelectOption(label="Scribe Mode", value="scribe", description="You control tone + biome")
            ]
        )
        
        async def mode_callback(interaction: discord.Interaction):
            selected_mode = mode_select.values[0].capitalize()
            self.session_mode = selected_mode
            
            try:
                if selected_mode == "Architect":
                    save_session_mode(interaction.guild.id, SessionModeManager.ARCHITECT)
                else:
                    save_session_mode(interaction.guild.id, SessionModeManager.SCRIBE)
            except:
                pass
            
            # Update embed to show new mode
            await interaction.response.defer()
            await interaction.message.edit(embed=self.update_embed(), view=self)
        
        mode_select.callback = mode_callback
        view.add_item(mode_select)
        
        await interaction.response.send_message("Select your game mode:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Launch Session", style=discord.ButtonStyle.primary, row=1)
    async def launch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Launch Session button - starts a new D&D session.
        
        IMPORTANT: Prologue is NO LONGER triggered here!
        Prologue now triggers in CharacterSelectionView.ready_btn() when all players press Ready.
        
        This button:
        1. Saves the active party
        2. Rolls destiny for all players/NPCs
        3. Fills party to 12 with spectral guardians if needed (Phase 1)
        4. Shows destiny roll results
        5. Prompts players to select their characters
        6. Waits for all players to press "Ready" (which triggers the prologue)
        
        Only the host can launch.
        """
        # ===== DISABLE BUTTON TO PREVENT DOUBLE-CLICKS =====
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        # ===== STATE VALIDATION =====
        # Prevent launching new session if one already exists
        config = get_dnd_config(interaction.guild.id)
        if config and config[2] and config[2] != "New Campaign Started.":
            await interaction.response.send_message(
                "⛔ **Cannot launch new session:** A saved game already exists.\n"
                "Use **Continue** to resume the saved session, or **Reset Campaign** to abandon it and start fresh.",
                ephemeral=True
            )
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("⛔ Only the host can launch the session.", ephemeral=True)
            # Re-enable button since we failed
            button.disabled = False
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            return
        
        # ===== VALIDATION: ENSURE PARTY EXISTS =====
        # Prevent launching with empty party
        if len(self.joined_users) == 0:
            await interaction.response.send_message(
                "⛔ **Cannot launch:** No players in the party.\n"
                "At least one player must press **Join** before launching.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Save current party to database
        save_active_party(interaction.guild.id, self.joined_users)
        
        # ===== DESTINY ROLLS =====
        # Roll destiny (narrative weight) for all players and NPCs
        rolls = {}
        for user_id in self.joined_users:
            if not str(user_id).startswith("npc_"):
                # Player gets 1-100 roll
                rolls[user_id] = random.randint(1, 100)
            else:
                # NPC gets 1-50 roll
                rolls[user_id] = random.randint(1, 50)
        
        # Solo player gets guaranteed maximum roll
        if len(self.joined_users) == 1:
            rolls[self.joined_users[0]] = 100
        
        # Save all destiny rolls to database
        batch_update_destiny(interaction.guild.id, rolls)
        
        # ===== FILL PARTY TO 12 (Phase 1 only) =====
        # If party is under 12 in Phase 1, manifest spectral guardians to fulfill prophecy
        if self.phase == 1 and len(self.joined_users) < 12 and not self.has_save:
            fill_count = 12 - len(self.joined_users)
            config = get_dnd_config(interaction.guild.id)
            quest_data = json.loads(config[10]) if config and config[10] else {"theme": "ocean"}
            theme = quest_data.get('theme', 'ocean')
            
            # Create guardian NPCs
            for i in range(fill_count):
                npc_id = f"npc_guardian_{i}"
                guardian_name = NPCNameGenerator.generate_name(theme, "guardian")
                
                # Save guardian character stats
                update_character(npc_id, interaction.guild.id, {
                    "name": guardian_name,
                    "hp": 30,
                    "max_hp": 30,
                    "ac": 15,
                    "is_npc": True,
                    "guardian_type": "Guardian"
                })
                
                # Intelligent NPC destiny capping: NPCs don't outshine players
                max_player_roll = max(rolls.values())
                npc_destiny = max(0, max_player_roll - random.randint(5, 15))
                update_character_destiny(npc_id, interaction.guild.id, npc_destiny)
                
                # Add to combat order
                add_combatant(
                    interaction.channel.id,
                    npc_id,
                    guardian_name,
                    random.randint(8, 12),
                    30, 30,
                    is_monster=2
                )
            
            # Announce guardian manifestation
            guardian_embed = discord.Embed(
                title="🛡️ Guardians Manifest",
                description=f"{fill_count} spectral guardians join your party to fulfill the prophecy of 12.",
                color=0x9B59B6
            )
            await interaction.followup.send(embed=guardian_embed)
        
        # ===== SHOW DESTINY ROLLS =====
        if rolls:
            roll_text = "\n".join([f"<@{uid}>: **{roll}**" for uid, roll in rolls.items() if not str(uid).startswith("npc_")])
            destiny_embed = discord.Embed(
                title="🔮 Destiny Rolls",
                description=roll_text,
                color=0x9B59B6
            )
            destiny_embed.set_footer(text="Higher roll = Greater narrative weight")
            await interaction.followup.send(embed=destiny_embed)
        
        # ===== CHARACTER SELECTION PHASE =====
        # Create character selection view - players must select before prologue starts
        char_selection_view = CharacterSelectionView(
            self.bot_cog, 
            interaction.guild.id, 
            self.joined_users,
            phase=self.phase,
            rulebook=self.rulebook
        )
        char_embed = discord.Embed(
            title="📋 Select Your Character",
            description="Each joined player must select a character.\nWhen all have selected, press **Ready** to begin the prologue.",
            color=0x3498DB
        )
        await interaction.followup.send(embed=char_embed, view=char_selection_view)
        
        # NOTE: Prologue is NOT called here anymore!
        # It will be triggered when all players press Ready in the CharacterSelectionView
        
        # Disable lobby buttons after launching
        for child in self.children:
            child.disabled = True
        
        try:
            await interaction.message.edit(view=self)
        except:
            pass
    
    @discord.ui.button(label="Reset Campaign", style=discord.ButtonStyle.danger, row=1)
    async def reset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Reset Campaign button - completely resets the campaign to Phase 1.
        Clears all progress, all character data, all session records.
        
        Only the host can reset the campaign.
        After reset, start a new session with /start_session.
        """
        # ===== HOST VALIDATION =====
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("⛔ Only the host can reset the campaign.", ephemeral=True)
            return
        
        # ===== STATE VALIDATION =====
        # Prevent reset if party is empty (nothing to reset)
        if len(self.joined_users) == 0:
            await interaction.response.send_message(
                "ℹ️ No active party to reset. The campaign is already in an empty state.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Call database reset function
            reset_campaign(interaction.guild.id, interaction.channel.id)
            
            # Confirm reset to user
            reset_embed = discord.Embed(
                title="🔄 Campaign Reset",
                description="The campaign has been completely reset to Phase 1.",
                color=0xE74C3C
            )
            reset_embed.add_field(
                name="What was reset",
                value="• All session data\n• All character progress\n• All campaign records\n• Phase reset to 1",
                inline=False
            )
            reset_embed.add_field(
                name="Next steps",
                value="Start a new session with /start_session",
                inline=False
            )
            
            await interaction.followup.send(embed=reset_embed)
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            
            try:
                await interaction.message.edit(view=self)
            except:
                pass
        except Exception as e:
            await interaction.followup.send(f"❌ Error resetting campaign: {str(e)}", ephemeral=True)

class DNDGameView(discord.ui.View):
    """
    In-game action view during D&D sessions.
    
    ROW 0: Action Selector dropdown (AI-suggested actions) OR Action Text Modal
    ROW 1: Roll Button (for ability checks, saves, etc.) & Take Action button
    ROW 2: Inspiration button (if player has Heroic Inspiration)
    
    This view is recreated for each turn to reflect current suggestions and game state.
    """
    
    def __init__(self, bot_cog, interaction, roll_needed=None, roll_reason=None, suggestions=None, rulebook="5e 2024", has_heroic_inspiration=False):
        """
        Initialize the in-game action view.
        
        Args:
            bot_cog: Reference to main cog for processing turns
            interaction: Current interaction context
            roll_needed: What the roll is for (attack, save, etc.)
            roll_reason: Human-readable reason for the roll
            suggestions: List of AI-suggested actions (max 4 will be shown)
            rulebook: Rules system ("5e 2024", etc.)
            has_heroic_inspiration: Whether player has inspiration available
        """
        super().__init__(timeout=180)
        self.bot_cog = bot_cog  # Reference to main cog
        self.interaction = interaction  # Current interaction for context
        self.roll_needed = roll_needed  # Type of roll (e.g., "d20+5")
        self.roll_reason = roll_reason  # Human reason for roll (e.g., "Perception Check")
        self.rulebook = rulebook  # Rules system being used
        self.has_heroic_inspiration = has_heroic_inspiration  # Player has inspiration available
        
        # ===== ROW 0: SUGGESTED ACTIONS DROPDOWN =====
        # AI suggests up to 4 possible actions for the player to choose from
        if suggestions and len(suggestions) > 0:
            options = []
            # Build select options from suggestions (max 4 to fit Discord limits)
            for i, suggestion in enumerate(suggestions[:4]):
                options.append(discord.SelectOption(
                    label=suggestion[:45],  # Discord label limit: 100 chars (truncate to 45 for safety)
                    value=str(i),  # Store index to identify which suggestion was chosen
                    description=suggestion[46:95] if len(suggestion) > 45 else None  # Optional description
                ))
            
            # Create the select menu
            select = discord.ui.Select(
                placeholder="Choose an action...",
                options=options,
                row=0  # Top row
            )
            select.callback = self.on_action_select  # Handle selection
            self.add_item(select)
        
        # ===== ROW 1: ROLL BUTTON (Conditional) =====
        # Show roll button only if a roll is needed (e.g., attack roll, save, check)
        if roll_needed and roll_reason:
            button = discord.ui.Button(
                label=f"🎲 {roll_reason[:20]}",  # Truncate reason to fit button
                style=discord.ButtonStyle.primary,  # Blue color for emphasis
                emoji="⚡",  # Lightning bolt icon for action
                row=1  # Middle row
            )
            button.callback = self.on_roll_button  # Process the roll
            self.add_item(button)
        
        # ===== ROW 1: TAKE ACTION BUTTON (Always available) =====
        # Players can always open modal to describe custom action
        action_btn = discord.ui.Button(
            label="⚔️ Take Action",  # Sword icon indicates combat/action
            style=discord.ButtonStyle.success,  # Green color for "go" action
            row=1  # Same row as roll button
        )
        action_btn.callback = self.on_action_button  # Open action modal
        self.add_item(action_btn)
        
        # ===== ROW 2: HEROIC INSPIRATION BUTTON (Conditional) =====
        # D&D 2024 feature: Players with inspiration can reroll after seeing result
        if "2024" in rulebook and has_heroic_inspiration:
            insp_btn = discord.ui.Button(
                label="✨ Use Inspiration",  # Sparkle icon for magical ability
                style=discord.ButtonStyle.secondary,  # Gray color for special ability
                row=2  # Bottom row
            )
            insp_btn.callback = self.on_inspiration_button  # Use inspiration
            self.add_item(insp_btn)
    
    async def on_action_select(self, interaction: discord.Interaction):
        """
        Handle player selecting a suggested action from dropdown.
        
        This processes the AI-suggested action they chose.
        """
        # Extract selected action index
        if interaction.data and 'values' in interaction.data:
            selected_index = int(interaction.data['values'][0])  # Get the selected option value as index
            # Get the corresponding suggestion from the dropdown options
            # The first child should be the select menu (if suggestions exist)
            if self.children and isinstance(self.children[0], discord.ui.Select):
                select = self.children[0]
                if selected_index < len(select.options):
                    selected_action = select.options[selected_index].label
                    # Run their turn with the selected action
                    await self.bot_cog.run_dnd_turn(interaction, selected_action, already_deferred=False)
                    return
            
            # Fallback if we can't find the suggestion (shouldn't happen)
            await self.bot_cog.run_dnd_turn(interaction, f"Action {selected_index + 1}", already_deferred=False)
    
    async def on_roll_button(self, interaction: discord.Interaction):
        """
        Handle player pressing the Roll button.
        
        This processes ability checks, saves, attack rolls, etc.
        """
        if self.roll_needed and self.roll_reason:
            # Run their turn requesting the specific roll type
            await self.bot_cog.run_dnd_turn(interaction, f"Roll: {self.roll_reason} [{self.roll_needed}]", already_deferred=False)
    
    async def on_action_button(self, interaction: discord.Interaction):
        """
        Handle player pressing Take Action button.
        
        Opens a modal where they can type a custom action description.
        """
        # Show the action modal for player input
        await interaction.response.send_modal(ActionModal(self.bot_cog))
    
    async def on_inspiration_button(self, interaction: discord.Interaction):
        """
        Handle player pressing Heroic Inspiration button (D&D 2024 only).
        
        Heroic Inspiration allows a player to reroll after seeing their result.
        """
        await interaction.response.defer()
        
        # Get player's character to check inspiration status
        char = get_character(interaction.user.id, interaction.guild.id)
        if char and char.get('heroic_inspiration', False):
            # Mark inspiration as used
            char['heroic_inspiration'] = False
            update_character(interaction.user.id, interaction.guild.id, char)
            
            # Run their turn requesting inspiration reroll
            await self.bot_cog.run_dnd_turn(
                interaction, 
                f"I use Heroic Inspiration to reroll! {self.roll_reason or 'Check'}"
            )

class ActionModal(discord.ui.Modal, title="Describe Your Action"):
    """
    Modal for players to describe a custom action.
    
    Appears when player clicks "Take Action" button.
    Allows free-form text description up to 300 characters.
    """
    
    # Text input field for the action description
    action = discord.ui.TextInput(
        label="What do you do?",
        placeholder="I attack the goblin, I search the room, I cast a spell...",
        style=discord.TextStyle.paragraph,  # Multi-line text
        max_length=300,  # Discord/DM limit
        required=True
    )
    
    def __init__(self, bot_cog):
        super().__init__()
        self.bot_cog = bot_cog  # Reference to main cog
    
    async def on_submit(self, interaction: discord.Interaction):
        """
        Process the submitted action description.
        
        Sends it to the DM AI for processing as a player turn.
        """
        await interaction.response.defer()
        # Process this as a normal player action turn
        await self.bot_cog.run_dnd_turn(interaction, self.action.value)

# --- MAIN COG ---
class DNDCog(commands.Cog):
    """Unified D&D Cog with 2024 rules only"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.cooldowns = {}
        self.rate_limit = 3
        
        RulebookRAG.init_rulebook_table()
        self._init_generational_tables()
        
        if not discord.opus.is_loaded():
            try:
                discord.opus.load_opus('libopus.so.0')
            except:
                pass
    
    def _init_generational_tables(self):
        """Initialize generational void cycle database tables"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Create dnd_session_mode table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_session_mode (
                guild_id TEXT PRIMARY KEY,
                session_mode TEXT DEFAULT 'Architect',
                custom_tone TEXT DEFAULT 'Standard',
                selected_biome TEXT DEFAULT 'forest',
                total_years_elapsed INTEGER DEFAULT 0,
                chronos_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create dnd_legacy_data table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_legacy_data (
                legacy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                character_name TEXT,
                character_class TEXT,
                character_level INTEGER,
                phase_number INTEGER,
                years_lived INTEGER,
                notable_deeds TEXT,
                bloodline_traits TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, character_name, phase_number)
            )''')
            
            # Create dnd_soul_remnants table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_soul_remnants (
                remnant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                character_name TEXT,
                class_name TEXT,
                level INTEGER,
                special_abilities TEXT,
                defeated BOOLEAN DEFAULT 0,
                phase_encountered INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Create dnd_chronicles table
            c.execute('''CREATE TABLE IF NOT EXISTS dnd_chronicles (
                chronicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT UNIQUE,
                phase_1_hero TEXT,
                phase_2_hero TEXT,
                phase_3_hero TEXT,
                victory_scroll TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            conn.commit()
            conn.close()
            print("✅ Generational system tables initialized")
        except Exception as e:
            print(f"⚠️ Warning initializing generational tables: {e}")
    
    def is_rate_limited(self, user_id) -> bool:
        """Simple rate limiting - handles both int and string IDs"""
        now = time.time()
        
        # Convert to string for consistent key usage
        if isinstance(user_id, int):
            user_key = str(user_id)
        else:
            user_key = str(user_id)  # Already string like "npc_guardian_0"
        
        if user_key in self.cooldowns:
            if now - self.cooldowns[user_key] < self.rate_limit:
                return True
        
        self.cooldowns[user_key] = now
        return False
    
    def validate_dnd_thread(self, interaction_or_channel):
        """Validate thread and return config data"""
        try:
            if hasattr(interaction_or_channel, 'channel'):
                channel = interaction_or_channel.channel
                guild_id = interaction_or_channel.guild.id
            else:
                channel = interaction_or_channel
                guild_id = channel.guild.id
            
            if not isinstance(channel, discord.Thread):
                return False, "❌ Not a D&D thread", None
            
            config = get_dnd_config(guild_id)
            if not config:
                return False, "❌ D&D not configured", None
            
            if int(config[0]) != channel.parent_id:
                return False, "❌ Invalid thread channel", None
            
            return True, config[1], config[2], config[3], config[4], "5e 2024", config[6], config[9] or "Narrative"
        
        except Exception as e:
            print(f"[DND] Validation error: {e}")
            return False, "❌ Configuration error", None
    
    async def get_dm_response(self, action: str, thread_id: int, location: str, summary: str, 
                            stats: str, guild_id: int, rulebook: str, mode: str, has_heroic_inspiration: bool, 
                            user_id: int = None) -> dict:
        """Optimized AI response generation with RAG, Architect Mode tone shifting, and Chain of Thought prompting"""
        
        # ===== TYPE SAFETY: Ensure action is a string =====
        # Handle edge cases where action might not be a string
        if not isinstance(action, str):
            action = str(action) if action else "Player takes action"
        
        # Get session mode to determine if automatic tone shifting is enabled
        try:
            session_mode_data = get_session_mode(guild_id)
            session_mode = session_mode_data[0] if session_mode_data else SessionModeManager.ARCHITECT
            current_tone = session_mode_data[1] if session_mode_data and len(session_mode_data) > 1 else "Standard"
        except:
            # Table might not exist yet during migration, use defaults
            session_mode = SessionModeManager.ARCHITECT
            current_tone = "Standard"
        
        # Auto-detect scene context for Architect Mode
        scene_context = "action"
        if "attack" in action.lower() or "fight" in action.lower():
            scene_context = "combat_start"
        elif "boss" in summary.lower() and ("defeated" in action.lower() or "kill" in action.lower()):
            scene_context = "boss_defeat"
        elif "time" in action.lower() and "skip" in action.lower():
            scene_context = "time_skip"
        
        # Apply automatic tone in Architect Mode (will persist once columns migrate)
        if session_mode == SessionModeManager.ARCHITECT:
            current_tone = AutomaticToneShifter.get_automatic_tone(scene_context)
            # Note: update_session_tone will be called after database migration
            # For now, tone is calculated but not persisted
        
        # Get character data for pre-computation
        char = None
        if user_id:
            char = get_character(user_id, guild_id)
        
        # Generate truth block with pre-computation
        truth_block = generate_truth_block(action, char)
        
        # Get relevant rules using RAG (enhanced with precision)
        rule_keywords = []
        words = action.lower().split()
        dnd_terms = ["cast", "attack", "save", "check", "spell", "ability", "skill", "rest", 
                     "damage", "hit", "critical", "advantage", "disadvantage", "concentration"]
        
        # Enhanced keyword extraction with specificity
        for word in words:
            if word in dnd_terms or any(term in word for term in ["fireball", "stealth", "concentration", "inspiration", "dice", "roll"]):
                # Add "mechanics" suffix for precision
                rule_keywords.append(f"{word} mechanics 5e")
        
        rule_context = ""
        for keyword in set(rule_keywords[:3]):
            # Use enhanced RAG lookup
            rules = RulebookRAG.lookup_rule(keyword, limit=2)
            if not rules:
                # Try without "mechanics" suffix
                fallback_keyword = keyword.replace(" mechanics 5e", "")
                rules = RulebookRAG.lookup_rule(fallback_keyword, limit=2)
            
            for rule_name, rule_text in rules:
                rule_context += f"[Rule: {rule_name}] {rule_text[:200]}\n\n"
        
        history = HistoryManager.get_optimized_history(thread_id, limit=6)
        context = "\n".join([f"{role}: {content[:100]}" for role, content in history])
        
        combatants = get_combat_order(thread_id)
        combat_text = "\n".join([
            f"{get_hp_emoji(hp, max_hp)} {name} ({hp}/{max_hp})" 
            for _, name, _, hp, max_hp, _, _ in combatants[:5]
        ]) if combatants else "No active combat."
        
        protagonist, destiny_score = get_session_protagonist(guild_id)
        phase, _ = get_dnd_campaign_data(guild_id)
        
        # Get tone context for prompt
        tone_context = AutomaticToneShifter.get_tone_context(current_tone)
        
        # Include explicit quest name and theme to reduce hallucinations about location
        quest_name = "Unknown"
        quest_theme = location
        try:
            cfg = get_dnd_config(guild_id)
            if cfg and cfg[10]:
                qd = json.loads(cfg[10]) if isinstance(cfg[10], str) else cfg[10]
                if isinstance(qd, dict):
                    quest_name = qd.get('name', quest_name)
                    quest_theme = qd.get('theme', quest_theme)
        except Exception:
            pass

        # ===== ENHANCED PROMPT WITH CHAIN OF THOUGHT =====
        prompt = f"""D&D DM Response Generator (2024 Rules) - CHAIN OF THOUGHT REQUIRED

{truth_block}

CURRENT GAME STATE:
- Quest: {quest_name}
- Quest Theme: {quest_theme}
- Current Location: {location}
- Game Mode: {mode}
- Campaign Phase: {phase}
- Narrative Tone: {current_tone} - {tone_context}
- Active Combatants: {combat_text}
- Party Status: {stats}
- Session Context: {summary[:200]}
- Protagonist: {protagonist or "None"} (Destiny Score: {destiny_score})

RELEVANT RULES (FROM RAG):
{rule_context}

RECENT HISTORY:
{context}

PLAYER ACTION: {action}

IMPORTANT: The current quest is set in a {quest_theme} environment. All descriptions should match this theme.

=== REQUIREMENTS FOR YOUR RESPONSE ===

STEP 1: MECHANICS CHECK (REQUIRED)
First, analyze the action against the TRUTH BLOCK values and RAG rules:
1. Confirm which specific rule from the RAG applies (or state "No specific rule found")
2. Explain how the TRUTH BLOCK values determine success/failure
3. Note any conditions, concentrations, or special effects that trigger

STEP 2: NARRATION (REQUIRED)
Second, write the narrative consequence (2-3 sentences) in the "{current_tone}" tone.

STEP 3: RESPONSE FORMAT (STRICT JSON)
Return exactly this JSON structure:
{{
  "mechanics_check": "Your step-by-step mechanical analysis here",
  "story": "Your narrative description here",
  "music": "{location}",
  "damage_events": [],
  "suggestions": ["action1", "action2", "action3"],
  "grant_heroic_inspiration": false
}}

CRITICAL INSTRUCTIONS:
- NEVER change the TRUTH BLOCK values
- If RAG context doesn't contain the rule, say in mechanics_check: "I am unsure of the specific rule, how would you like to handle this?"
- Use Species terminology, not Race
- On natural 20, grant Heroic Inspiration
- For phase {phase}, advance story appropriately
- Heroic Inspiration allows rerolls after seeing result
"""
        
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: GROQ_CLIENT.chat.completions.create(
                        model=FAST_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=500,  # Increased for CoT
                        response_format={"type": "json_object"}
                    )
                ),
                timeout=25.0  # Slightly longer for CoT
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Extract mechanics check for logging/debugging
            if "mechanics_check" in result:
                # You might want to log or display this separately
                pass
            
            # Ensure story field exists
            if "story" not in result:
                result["story"] = "The story continues..."
            
            return result
            
        except asyncio.TimeoutError:
            return {
                "mechanics_check": "Timeout analyzing mechanics",
                "story": "The Dungeon Master ponders your action...",
                "music": location,
                "suggestions": ["Wait", "Investigate", "Attack"],
                "grant_heroic_inspiration": False
            }
        except Exception as e:
            print(f"[DND] AI Error: {e}")
            return {
                "mechanics_check": f"Error in analysis: {str(e)[:50]}",
                "story": "The threads of fate tremble with your decision...",
                "music": location,
                "suggestions": ["Proceed cautiously", "Regroup"],
                "grant_heroic_inspiration": False
            }
    
    async def launch_game_logic(self, interaction: discord.Interaction, phase: int, rulebook: str, is_continue: bool = False):
        """
        Launch or continue a game session.
        
        Args:
            interaction: Discord interaction
            phase: Campaign phase (1, 2, or 3)
            rulebook: D&D rulebook version (e.g., "5e 2024")
            is_continue: If True, resumes existing session without prologue
        """
        update_game_mode(interaction.guild.id, "Narrative")
        
        config = get_dnd_config(interaction.guild.id)
        quest_data = None
        
        # ===== LOAD QUEST DATA SAFELY =====
        if config and config[10]:
            try:
                # Parse quest data from config
                if isinstance(config[10], str):
                    quest_data = json.loads(config[10])
                elif isinstance(config[10], dict):
                    quest_data = config[10]
                else:
                    quest_data = None
            except Exception as e:
                print(f"[launch_game_logic] Error parsing quest_data: {e}")
                quest_data = None
        
        # ===== CREATE DEFAULT QUEST IF NEEDED =====
        if not quest_data or not isinstance(quest_data, dict):
            # Prefer using the saved current location from config so we don't randomize
            current_location = (config[1].lower() if config and config[1] else "").strip() if config else ""

            # Map common location synonyms to our conquest keys
            if current_location in ["ocean", "sea", "water"]:
                theme = "ocean"
            elif current_location in ["desert", "sands", "dune"]:
                theme = "desert"
            elif current_location in ["volcano", "lava", "fire"]:
                theme = "volcano"
            elif current_location in ["forest", "woods"]:
                theme = "forest"
            elif current_location in ["tavern", "city"]:
                theme = current_location or "tavern"
            else:
                # Fallback to ocean if unknown
                theme = "ocean"

            if theme in CONQUEST_PATHS:
                quest_data = CONQUEST_PATHS[theme]["p1"].copy()
            else:
                # final fallback
                theme = "ocean"
                quest_data = CONQUEST_PATHS[theme]["p1"].copy()

            quest_data["path_key"] = theme
            # Persist a safe JSON representation
            try:
                update_quest_data(interaction.guild.id, json.dumps(quest_data))
            except Exception:
                # best-effort; not fatal
                pass

        # ===== ENSURE QUEST_DATA IS ALWAYS A DICT =====
        if not isinstance(quest_data, dict):
            theme = "ocean"
            quest_data = CONQUEST_PATHS[theme]["p1"].copy()
            quest_data["path_key"] = theme

        # Ensure the stored config location matches the quest theme; set if missing
        try:
            conf_loc = (config[1].lower() if config and config[1] else "").strip()
        except Exception:
            conf_loc = ""

        quest_theme = quest_data.get("theme", quest_data.get("path_key", "ocean")).lower() if isinstance(quest_data, dict) else "ocean"

        # If the config location is empty, set it to the quest theme
        if not conf_loc:
            try:
                update_dnd_location(interaction.guild.id, quest_theme)
            except Exception:
                pass
        else:
            # If they disagree (e.g., config says 'ocean' but quest_data theme is 'desert'), prefer quest theme
            if quest_theme and quest_theme not in conf_loc and not any(x in conf_loc for x in [quest_theme, "tavern"]):
                try:
                    update_dnd_location(interaction.guild.id, quest_theme)
                except Exception:
                    pass
        
        # ===== DETERMINE IF RESUMING EXISTING SESSION =====
        # Check both is_continue parameter and existing campaign summary
        is_resume = is_continue or (config and config[2] and config[2] != "New Campaign Started.")
        
        # ===== SAFELY GET QUEST NAME =====
        quest_name = quest_data.get('name', 'Adventure') if isinstance(quest_data, dict) else 'Adventure'
        quest_theme = quest_data.get('theme', quest_data.get('path_key', 'forest')) if isinstance(quest_data, dict) else 'forest'
        
        if is_resume:
            # RESUME EXISTING SESSION - Use existing summary (no prologue)
            story = config[2] if config and config[2] else "Your adventure continues..."
            title = f"↩️ {quest_name} (Resumed)"
        else:
            # NEW SESSION - Show prologue with narrative setup
            story = f"**{quest_name}**\n\nYour adventure begins in a {quest_theme} setting. The prophecy of 12 heroes must be fulfilled. What will you do first?"
            title = f"📖 {quest_name}"
            update_dnd_summary(interaction.guild.id, story)
        
        embed = discord.Embed(
            title=title,
            description=story,
            color=LOCATION_THEMES.get(quest_theme, 0x3498DB)
        )
        embed.add_field(name="Rules", value="2024 Edition", inline=True)
        embed.add_field(name="Location", value=quest_theme.title(), inline=True)
        embed.set_footer(text="Vespera // Where legends are written")
        
        # Use different action suggestions based on resume vs new
        if is_resume:
            suggestions = ["Continue exploring", "Check inventory", "Regroup with allies", "Assess situation"]
        else:
            suggestions = ["Explore the area", "Talk to locals", "Check equipment", "Form a plan"]
        
        view = DNDGameView(
            self, 
            interaction,
            suggestions=suggestions
        )
        
        await interaction.followup.send(embed=embed, view=view)
        
        # Log the session event
        if is_resume:
            add_dnd_history(interaction.channel.id, "DM", f"Session resumed: {quest_name}")
        else:
            add_dnd_history(interaction.channel.id, "DM", f"Session started: {quest_name}")
    
    async def run_dnd_turn(self, interaction: discord.Interaction, action: str, already_deferred: bool = True):
        """
        Process a player's action/turn in the D&D game.
        
        This method:
        1. Validates the player is in a D&D thread
        2. Gets the DM's AI response to the player's action
        3. Updates game state (location, HP, conditions, etc.)
        4. Displays results with ASCII map, combatants, and available actions
        5. Shows destiny roll (if available) and previous roll caching
        
        Args:
            interaction: Discord interaction from the player
            action: What the player wants to do (text description or action selection)
            already_deferred: Whether response already deferred (skip defer if True)
        """
        # ===== RATE LIMITING =====
        # Prevent spam by rate limiting turns
        if self.is_rate_limited(interaction.user.id):
            if not already_deferred:
                await interaction.response.defer()
            await interaction.followup.send("⏳ Please wait a moment before your next action.", ephemeral=True)
            return
        
        # ===== DEFER RESPONSE =====
        # Discord requires us to acknowledge interaction within 3 seconds
        if not already_deferred:
            await interaction.response.defer()
        
        # ===== VALIDATE D&D CONTEXT =====
        # Make sure this is a valid D&D thread with proper config
        valid, *config_data = self.validate_dnd_thread(interaction)
        if not valid:
            await interaction.followup.send(config_data[0], ephemeral=True)
            return
        
        # Extract config: location, summary, (unused), (unused), rulebook, (unused), mode
        location, summary, _, _, rulebook, _, mode = config_data
        
        # ===== GET PLAYER CHARACTER =====
        # Fetch the player's character sheet
        char = get_character(interaction.user.id, interaction.guild.id)
        stats = f"{char.get('name', 'Unknown')}: {char.get('hp', 0)}/{char.get('max_hp', 1)} HP" if char else "Unknown character"
        
        # ===== LOG ACTION TO HISTORY =====
        # Record this action in the session history for context in future turns
        add_dnd_history(interaction.channel.id, interaction.user.display_name, action[:200])
        
        # ===== GET AI DM RESPONSE =====
        # Call Groq API to get DM's narrative response to the player's action
        dm_response = await self.get_dm_response(
            action, interaction.channel.id, location, summary, stats,
            interaction.guild.id, rulebook, mode, char.get('heroic_inspiration', False) if char else False,
            user_id=interaction.user.id
        )
        
        # Extract key data from DM response
        story = dm_response.get("story", "The story continues...")
        mechanics_check = dm_response.get("mechanics_check", "")
        new_location = dm_response.get("music", location)  # "music" is location in response format
        
        # ===== UPDATE GAME STATE =====
        # Persist changes to the database
        if new_location != location:
            update_dnd_location(interaction.guild.id, new_location)
        
        update_dnd_summary(interaction.guild.id, story[:500])  # Update session summary
        add_dnd_history(interaction.channel.id, "DM", story[:300])  # Log DM response
        
        # ===== GRANT HEROIC INSPIRATION (D&D 2024) =====
        # Natural 20s or critical successes grant inspiration for future rerolls
        if dm_response.get("grant_heroic_inspiration") and char:
            char['heroic_inspiration'] = True
            update_character(interaction.user.id, interaction.guild.id, char)
        
        # ===== PROCESS DAMAGE EVENTS =====
        # Handle any damage dealt to combatants
        updates = []
        damage_events = dm_response.get("damage_events", [])
        
        for event in damage_events:
            target = event.get("target", "")
            amount = event.get("amount", 0)
            
            # Find matching combatant and apply damage
            combatants = get_combat_order(interaction.channel.id)
            for combatant in combatants:
                cid, cname, _, _, _, is_monster, _ = combatant
                if target.lower() in cname.lower():
                    # Update combatant HP
                    new_hp = update_combatant_hp(interaction.channel.id, cid, -amount)
                    
                    # Check for concentration saves (if they're concentrating on a spell)
                    conditions = get_combatant_conditions(interaction.channel.id, cid)
                    if "concentrating" in conditions.lower() and amount > 0:
                        dc = max(10, amount // 2)  # DC = damage / 2, minimum 10
                        updates.append(f"⚠️ **{cname} needs CON Save (DC {dc}) to maintain concentration!**")
                    
                    # Log HP change
                    updates.append(f"{cname}: {new_hp} HP ({-amount} damage)")
                    
                    # Remove dead monsters from combat
                    if new_hp <= 0 and is_monster == 1:
                        remove_combatant(interaction.channel.id, cid)
                        updates.append(f"💀 {cname} defeated!")
                    
                    # Update player character HP if they took damage
                    if cid == str(interaction.user.id) and char:
                        char['hp'] = new_hp
                        update_character(interaction.user.id, interaction.guild.id, char)
        
        # ===== BUILD RESPONSE EMBED =====
        # Create the Discord embed to show the DM's narrative response
        embed = discord.Embed(
            description=story,  # DM's narrative
            color=LOCATION_THEMES.get(new_location, 0x3498DB)  # Color based on location
        )
        
        # Set author as the player who took the action
        embed.set_author(
            name=f"🎲 {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        
        # ===== ADD ASCII MAP (if available) =====
        # Try to add an ASCII representation of the current location/combat
        try:
            # Get current location theme
            location_theme = LOCATION_THEMES.get(new_location, "dungeon")
            
            # Generate ASCII map based on location
            # Format: Simple ASCII grid representing the area
            ascii_map = f"```\n┌─────────────────────┐\n│  {new_location.upper():^17}  │\n└─────────────────────┘\n```"
            
            # Get active combatants to show on map
            combatants = get_combat_order(interaction.channel.id)
            if combatants:
                # Build combatant list with HP bars
                combat_ascii = "```\nActive Combatants:\n"
                for cid, cname, init, hp, max_hp, is_monster, _ in combatants[:5]:
                    # Calculate HP bar (20 characters)
                    bar_filled = int((hp / max_hp) * 20) if max_hp > 0 else 0
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)
                    combat_ascii += f"{cname}: [{bar}] {hp}/{max_hp}\n"
                combat_ascii += "```"
                
                # Only add if not too long
                if len(combat_ascii) < 1024:
                    embed.add_field(name="⚔️ Battle Map", value=combat_ascii, inline=False)
        except:
            pass  # Gracefully skip ASCII map if error
        
        # ===== ADD MECHANICS CHECK (if available) =====
        # Show the AI's mechanical analysis of the action
        if mechanics_check and len(mechanics_check) > 10:
            embed.add_field(
                name="⚙️ Mechanics Analysis",
                value=mechanics_check[:200] + ("..." if len(mechanics_check) > 200 else ""),
                inline=False
            )
        
        # Get user's preferred language for footer
        user_lang = get_target_language(interaction.user.id)
        embed.set_footer(text=f"Language: {user_lang}" if user_lang and user_lang != "English" else "Language: English")
        
        # ===== ADD GAME UPDATES (damage, status, etc.) =====
        # Show any mechanical changes that occurred this turn
        if updates:
            embed.add_field(
                name="⚡ Updates",
                value="\n".join(updates[:5]),  # Max 5 updates per turn
                inline=False
            )
        
        # ===== ADD PLAYER STATUS =====
        # Show the acting player's current HP and status
        if char:
            embed.add_field(
                name="💚 Your Status",
                value=f"{char.get('hp', 0)}/{char.get('max_hp', 1)} HP",
                inline=True
            )
            
            # ===== SHOW HEROIC INSPIRATION AVAILABILITY =====
            # D&D 2024: Show if player has inspiration to spend on reroll
            if char.get('heroic_inspiration', False):
                embed.add_field(
                    name="✨ Heroic Inspiration",
                    value="Available (use to reroll)",
                    inline=True
                )
        
        # ===== GET DESTINY ROLL (if available) =====
        # Show player's destiny score and if they've already rolled
        try:
            # Get this player's destiny roll from the launch
            protagonist, destiny_score = get_session_protagonist(interaction.guild.id)
            if protagonist == interaction.user.id or protagonist is None:
                # Show destiny roll as a persistent stat
                embed.add_field(
                    name="🔮 Destiny Roll",
                    value=f"**{destiny_score}**",
                    inline=True
                )
        except:
            pass  # Skip if destiny system not available
        
        # ===== CREATE ACTION VIEW =====
        # Build buttons/dropdowns for next action
        view = DNDGameView(
            self,
            interaction,
            suggestions=dm_response.get("suggestions", ["Continue", "Investigate", "Rest"]),
            rulebook=rulebook,
            has_heroic_inspiration=char.get('heroic_inspiration', False) if char else False
        )
        
        # ===== SEND RESPONSE =====
        # Post the embed with action buttons
        await interaction.followup.send(embed=embed, view=view)
    
    # --- BASIC COMMANDS ---
    
    @app_commands.command(name="setup_dnd", description="Configure D&D for this server")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_dnd(self, interaction: discord.Interaction, 
                       channel: discord.TextChannel,
                       role: discord.Role = None):
        """Set up D&D with parent channel and optional role restriction - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can configure D&D!",
                ephemeral=True
            )
            return
        
        role_id = role.id if role else None
        save_dnd_config(interaction.guild.id, channel.id, role_id)
        
        embed = discord.Embed(
            title="🎲 D&D Configured (2024 Rules)",
            description=f"Dungeons & Dragons has been configured for {channel.mention}",
            color=0x3498DB
        )
        if role:
            embed.add_field(name="Role Restriction", value=role.mention)
        embed.add_field(name="Configured by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Use /start_session to begin")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="start_session", description="Start or continue a D&D session")
    @is_dnd_player()
    async def start_session(self, interaction: discord.Interaction):
        """Start a new session or continue existing one"""
        # ===== IMMEDIATE DEFER (Required within 3 seconds) =====
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction expired, can't respond
            print("[start_session] Interaction expired before defer")
            return
        except Exception as e:
            print(f"[start_session] Defer error: {e}")
            return
        
        try:
            if not await validate_dnd_access(interaction):
                embed = discord.Embed(
                    title="⛔ Access Denied",
                    description="You don't have permission to start D&D sessions.",
                    color=0xE74C3C
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            valid, *_ = self.validate_dnd_thread(interaction)
            if not valid:
                await interaction.followup.send("❌ This is not a valid D&D thread.", ephemeral=True)
                return
            
            # Get config with timeout protection
            try:
                phase, legends = get_dnd_campaign_data(interaction.guild.id)
                config = get_dnd_config(interaction.guild.id)
            except Exception as e:
                print(f"[start_session] Config error: {e}")
                phase, legends = 1, []
                config = None
            
            has_save = config and config[2] and config[2] != "New Campaign Started."
            
            quest_title = "Adventure Awaits"
            if config and config[10]:
                try:
                    quest_data = json.loads(config[10])
                    quest_title = quest_data.get('name', quest_title)
                except:
                    pass
            
            view = SessionLobbyView(
                self,
                interaction,
                phase,
                has_save,
                quest_title=quest_title,
                legends=legends
            )
            
            embed = view.update_embed()
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"[start_session] Error: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Error starting session: {str(e)[:100]}",
                    ephemeral=True
                )
            except:
                pass
    
    
    @app_commands.command(name="do", description="Perform an action in the D&D session")
    @is_dnd_player()
    async def do_action(self, interaction: discord.Interaction, action: str):
        """Perform an action (rate limited)"""
        if len(action) > 300:
            await interaction.response.send_message("❌ Action too long (max 300 characters)", ephemeral=True)
            return
        
        await self.run_dnd_turn(interaction, action)
    
    @app_commands.command(name="import_character", description="Import character from D&D Beyond or text")
    @is_dnd_player()
    async def import_character(self, interaction: discord.Interaction, character_text: str):
        """Import character sheet"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            lines = character_text.split('\n')
            char_data = {
                "name": "Adventurer",
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "heroic_inspiration": False,
                "weapon_masteries": []
            }
            
            for line in lines[:20]:
                line_lower = line.lower()
                if "name:" in line_lower:
                    char_data["name"] = line.split(":", 1)[1].strip()
                elif "hp:" in line_lower or "hit points:" in line_lower:
                    try:
                        hp_part = line.split(":", 1)[1].strip()
                        if "/" in hp_part:
                            current, max_hp = hp_part.split("/")
                            char_data["hp"] = int(current.strip())
                            char_data["max_hp"] = int(max_hp.strip())
                        else:
                            char_data["hp"] = int(hp_part)
                            char_data["max_hp"] = int(hp_part)
                    except:
                        pass
                elif "ac:" in line_lower or "armor class:" in line_lower:
                    try:
                        char_data["ac"] = int(line.split(":", 1)[1].strip())
                    except:
                        pass
                # Migrate from old keys
                if "race:" in line_lower:
                    char_data["species"] = line.split(":", 1)[1].strip()
            
            update_character(interaction.user.id, interaction.guild.id, char_data)
            
            embed = discord.Embed(
                title="✅ Character Imported",
                description=f"**{char_data['name']}** ready for adventure!",
                color=0x2ECC71
            )
            embed.add_field(name="HP", value=f"{char_data['hp']}/{char_data['max_hp']}", inline=True)
            embed.add_field(name="AC", value=str(char_data['ac']), inline=True)
            if 'species' in char_data:
                embed.add_field(name="Species", value=char_data['species'], inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error importing character: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="roll_initiative", description="Roll initiative for combat")
    @is_dnd_player()
    async def roll_initiative(self, interaction: discord.Interaction):
        """Roll initiative and start combat mode"""
        await interaction.response.defer()
        
        valid, *_ = self.validate_dnd_thread(interaction)
        if not valid:
            await interaction.followup.send("❌ Not a valid D&D thread", ephemeral=True)
            return
        
        update_game_mode(interaction.guild.id, "Combat")
        
        char = get_character(interaction.user.id, interaction.guild.id)
        char_name = char.get('name', interaction.user.display_name) if char else interaction.user.display_name
        
        initiative = random.randint(1, 20)
        if char and 'dex' in char:
            initiative += (char['dex'] - 10) // 2
        
        add_combatant(
            interaction.channel.id,
            interaction.user.id,
            char_name,
            initiative,
            char.get('hp', 10) if char else 10,
            char.get('max_hp', 10) if char else 10
        )
        
        combatants = get_combat_order(interaction.channel.id)
        
        embed = discord.Embed(
            title="⚔️ Initiative Rolled",
            description=f"{char_name} rolls **{initiative}** for initiative!",
            color=0xE74C3C
        )
        
        if combatants:
            order = "\n".join([f"{i+1}. {name} ({score})" for i, (_, name, score, _, _, _, _) in enumerate(combatants)])
            embed.add_field(name="Combat Order", value=order, inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="long_rest", description="Take a long rest to heal and recover")
    @is_dnd_player()
    async def long_rest(self, interaction: discord.Interaction):
        """Take a long rest"""
        await interaction.response.defer()
        
        perform_long_rest_db(interaction.channel.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="⛺ Long Rest Complete",
            description="The party rests, recovering hit points and abilities.",
            color=0x3498DB
        )
        embed.add_field(name="Effects", value="• Full HP recovery\n• Conditions removed\n• Heroic Inspiration regained", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="time_skip", description="Advance to next Phase with randomized time skip")
    @app_commands.default_permissions(manage_guild=True)
    async def time_skip(self, interaction: discord.Interaction):
        """Advance campaign phase with dynamic Chronos Engine (randomized time skips)"""
        await interaction.response.defer()
        
        phase, _ = get_dnd_campaign_data(interaction.guild.id)
        
        # Determine target phase
        if phase == 1:
            target_phase = 2
        elif phase == 2:
            target_phase = 3
        else:
            await interaction.followup.send("❌ Campaign already complete (Phase 3)", ephemeral=True)
            return
        
        # Generate randomized time skip using Chronos Engine
        years, time_flavor = TimeSkipManager.generate_time_skip(target_phase)
        generations = TimeSkipManager.calculate_generations(years)
        
        # Update total years elapsed
        total_years = update_total_years(interaction.guild.id, years)
        
        config = get_dnd_config(interaction.guild.id)
        party = json.loads(config[6]) if config and config[6] else []
        
        # For Phase 2->3 transition, create legacy data and soul remnants
        if target_phase == 3:
            for user_id in party:
                if not str(user_id).startswith("npc_"):
                    char = get_character(user_id, interaction.guild.id)
                    if char:
                        legacy_data = {
                            "user_id": user_id,
                            "p2_character_name": char.get('name', 'Unknown'),
                            "class": char.get('class', 'Unknown'),
                            "destiny_roll": char.get('destiny_roll', 0),
                            "time_skip_years": years,
                            "biome_conquered": config[1] if config else 'unknown'
                        }
                        legacy_data["signature_move"] = f"{char.get('name', 'Legend')}'s Legendary Strike"
                        legacy_data["legacy_buff"] = LevelProgression.generate_legacy_buff(legacy_data)
                        
                        # Save to legacy system
                        save_legacy_data(interaction.guild.id, user_id, char.get('name', 'Unknown'), legacy_data)
        
        # Store surviving legends
        legends = []
        for user_id in party:
            if not str(user_id).startswith("npc_"):
                char = get_character(user_id, interaction.guild.id)
                if char:
                    legends.append({
                        "id": user_id,
                        "name": char.get('name', f"Player {user_id}"),
                        "status": "Legend" if target_phase == 2 else "Ancestor",
                        "phase": phase,
                        "destiny_roll": char.get('destiny_roll', 0)
                    })
        
        advance_campaign_phase(interaction.guild.id, target_phase, legends)
        
        # Update quest to next phase
        if config and config[10]:
            try:
                quest_data = json.loads(config[10])
                path_key = quest_data.get('path_key', random.choice(list(VOID_CYCLE_BIOMES.keys())))
                if path_key in VOID_CYCLE_BIOMES:
                    biome_key = f"p{target_phase}" if target_phase in [2, 3] else "p1"
                    if biome_key in VOID_CYCLE_BIOMES[path_key]:
                        update_quest_data(interaction.guild.id, json.dumps(VOID_CYCLE_BIOMES[path_key][biome_key]))
                        update_dnd_location(interaction.guild.id, path_key)
            except:
                pass
        
        # Create narrative summary for time skip
        summary = f"**{years} Years Have Passed...**\n\n"
        if target_phase == 2:
            summary += f"{time_flavor}\n\nThe legends must face new threats in an changed world. {generations['generations']} generations have come and gone."
        else:  # Phase 3
            summary += f"{time_flavor}\n\nThe descendants of heroes must break the cycle. {generations['generations']} generations separate them from their ancestors' glory."
        
        update_dnd_summary(interaction.guild.id, summary)
        
        # Create detailed embed with Chronos Engine info
        embed = discord.Embed(
            title="⏳ Chronos Engine: Time Skip",
            description=time_flavor,
            color=0xF1C40F
        )
        embed.add_field(name="Years Elapsed", value=f"{years} years", inline=True)
        embed.add_field(name="Phase Transition", value=f"Phase {phase} → Phase {target_phase}", inline=True)
        embed.add_field(name="Generations Passed", value=f"{generations['generations']} generations (~{generations['generations'] * 25} years each)", inline=False)
        embed.add_field(name="Dynasties Changed", value=str(generations['dynasties']), inline=True)
        embed.add_field(name="Total Time Elapsed", value=f"{total_years} years since campaign start", inline=True)
        embed.add_field(name="Cultural Shifts", value=f"{generations['cultural_shifts']} major shifts", inline=False)
        embed.add_field(name="Surviving Legends", value=str(len(legends)) if legends else "None", inline=True)
        
        if target_phase == 3:
            embed.add_field(name="🔮 Phase 3 Info", value="New generation characters must be created. Phase 1/2 characters become Soul Remnants.", inline=False)
        
        embed.set_footer(text="The world has shifted. Old heroes fade to legend.")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="roll_destiny", description="Roll for protagonist status (d100)")
    @is_dnd_player()
    async def roll_destiny(self, interaction: discord.Interaction):
        """Roll destiny score for narrative weight"""
        char = get_character(interaction.user.id, interaction.guild.id)
        if not char:
            await interaction.response.send_message("❌ Import a character sheet first", ephemeral=True)
            return
        
        roll = random.randint(1, 100)
        update_character_destiny(interaction.user.id, interaction.guild.id, roll)
        
        protagonist, score = get_session_protagonist(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔮 Destiny Roll",
            description=f"{char.get('name', interaction.user.display_name)} rolls **{roll}**",
            color=0x9B59B6
        )
        embed.add_field(name="Your Roll", value=f"🎲 **{roll}**", inline=True)
        
        if protagonist:
            embed.add_field(name="Current Protagonist", value=f"👑 {protagonist} ({score})", inline=True)
        
        if roll >= 80:
            embed.add_field(name="Destiny", value="**Major Plot Figure**", inline=False)
        elif roll >= 50:
            embed.add_field(name="Destiny", value="**Important Character**", inline=False)
        else:
            embed.add_field(name="Destiny", value="**Supporting Role**", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="end_session", description="End the current D&D session")
    @is_dnd_player()
    async def end_session(self, interaction: discord.Interaction):
        """Cleanly end the session and disable all views"""
        # ===== IMMEDIATE DEFER (Required within 3 seconds) =====
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction expired, can't respond
            print("[end_session] Interaction expired before defer")
            return
        except Exception as e:
            print(f"[end_session] Defer error: {e}")
            return
        
        try:
            clear_combat(interaction.channel.id)
            
            # Disable all views in the channel
            try:
                async for message in interaction.channel.history(limit=50):
                    if message.components:
                        try:
                            await message.edit(view=None)
                        except:
                            pass
            except:
                pass
            
            if interaction.guild.id in self.voice_clients:
                vc = self.voice_clients[interaction.guild.id]
                if vc and vc.is_connected():
                    await vc.disconnect()
                self.voice_clients.pop(interaction.guild.id, None)
            
            embed = discord.Embed(
                title="🎬 Session Ended",
                description=f"Session ended by {interaction.user.mention}\nAll interactive elements have been disabled.",
                color=0x95A5A6
            )
            embed.set_footer(text="Use /start_session to continue your adventure")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[end_session] Error: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Error ending session: {str(e)[:100]}",
                    ephemeral=True
                )
            except:
                pass
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="reset_campaign", description="Reset campaign to Phase 1")
    @app_commands.default_permissions(manage_guild=True)
    async def reset_campaign_cmd(self, interaction: discord.Interaction):
        """Reset campaign data - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can reset campaigns!",
                ephemeral=True
            )
            return
        
        reset_campaign(interaction.guild.id, interaction.channel.id)
        
        theme = random.choice(list(CONQUEST_PATHS.keys()))
        quest_data = CONQUEST_PATHS[theme]["p1"]
        quest_data["path_key"] = theme
        update_quest_data(interaction.guild.id, json.dumps(quest_data))
        update_dnd_location(interaction.guild.id, quest_data["theme"])
        
        await interaction.followup.send(
            f"🔄 Campaign reset! New quest: **{quest_data['name']}** (reset by {interaction.user.mention})", 
            ephemeral=True
        )
    
    @app_commands.command(name="add_lore", description="Add lore to the campaign")
    @app_commands.default_permissions(manage_guild=True)
    async def add_lore(self, interaction: discord.Interaction, topic: str, description: str):
        """Manually add lore - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can add lore!",
                ephemeral=True
            )
            return
        
        if len(topic) > 100 or len(description) > 500:
            await interaction.followup.send("❌ Topic or description too long", ephemeral=True)
            return
        
        add_lore(interaction.guild.id, topic, description)
        
        embed = discord.Embed(
            title="📖 Lore Added",
            description=f"**{topic}**\n\n{description}",
            color=0x3498DB
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="campaign_status", description="Check current campaign status")
    @is_dnd_player()
    async def campaign_status(self, interaction: discord.Interaction):
        """Display campaign information"""
        await interaction.response.defer()
        
        phase, legends = get_dnd_campaign_data(interaction.guild.id)
        config = get_dnd_config(interaction.guild.id)
        
        quest_name = "Unknown Quest"
        quest_theme = "tavern"
        if config and config[10]:
            try:
                quest_data = json.loads(config[10])
                quest_name = quest_data.get('name', quest_name)
                quest_theme = quest_data.get('theme', quest_theme)
            except:
                pass
        
        embed = discord.Embed(
            title="📊 Campaign Status (2024)",
            color=LOCATION_THEMES.get(quest_theme, 0x3498DB)
        )
        
        embed.add_field(name="Quest", value=quest_name, inline=True)
        embed.add_field(name="Phase", value=str(phase), inline=True)
        embed.add_field(name="Rules", value="2024 Edition", inline=True)
        
        if config and config[1]:
            embed.add_field(name="Current Location", value=config[1], inline=False)
        
        if config and config[2]:
            summary = config[2][:200] + "..." if len(config[2]) > 200 else config[2]
            embed.add_field(name="Story Summary", value=summary, inline=False)
        
        if phase > 1 and legends:
            legend_names = [l.get('name', 'Unknown') for l in legends[:5]]
            legends_text = ", ".join(legend_names)
            if len(legends) > 5:
                legends_text += f" and {len(legends) - 5} more..."
            embed.add_field(name="Legends", value=legends_text, inline=False)
        
        protagonist, score = get_session_protagonist(interaction.guild.id)
        if protagonist:
            embed.add_field(name="Protagonist", value=f"{protagonist} (Destiny: {score})", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    # --- ENHANCED COMMANDS ---
    
    @app_commands.command(name="rule", description="Look up a D&D rule with precision filtering")
    @app_commands.describe(keyword="Rule to look up (e.g., 'fireball', 'concentration')", 
                           precise="Use precision filtering (default: True)")
    async def rule_lookup(self, interaction: discord.Interaction, keyword: str, precise: bool = True):
        """Rulebook RAG lookup with precision filtering"""
        await interaction.response.defer()
        
        rules = RulebookRAG.lookup_rule(keyword, limit=3, require_precision=precise)
        
        if not rules:
            await interaction.followup.send(
                f"No rules found for '{keyword}'. Try being more specific or disable precision filtering.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(title=f"📚 Rule: {keyword}", color=0x3498DB)
        
        for i, (rule_name, rule_text) in enumerate(rules, 1):
            embed.add_field(
                name=f"{i}. {rule_name.title()}",
                value=rule_text[:250] + ("..." if len(rule_text) > 250 else ""),
                inline=False
            )
        
        if precise:
            embed.set_footer(text="Precision filtering enabled - showing most relevant rules")
        else:
            embed.set_footer(text="Broad search - may include less relevant results")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="add_rule", description="Add a custom rule to the rulebook")
    @app_commands.default_permissions(manage_guild=True)
    async def add_rule_cmd(self, interaction: discord.Interaction, 
                          keyword: str, 
                          rule_text: str,
                          rule_type: str = "custom"):
        """Add custom rule - Moderators/Server Owners only"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user has manage_guild permission or is owner
        if not (interaction.user.guild_permissions.manage_guild or 
                interaction.user.id == interaction.guild.owner_id):
            await interaction.followup.send(
                "❌ Only server moderators and owners can add rules!",
                ephemeral=True
            )
            return
        
        RulebookRAG.add_rule(keyword, rule_text, rule_type, "custom")
        
        embed = discord.Embed(
            title="✅ Rule Added",
            description=f"**{keyword}** added to rulebook",
            color=0x2ECC71
        )
        embed.add_field(name="Rule", value=rule_text[:200], inline=False)
        embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Type", value=rule_type, inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="spell", description="Look up a spell from SRD")
    async def spell_lookup(self, interaction: discord.Interaction, spell_name: str):
        """SRD spell lookup using database"""
        await interaction.response.defer()
        
        # Try to get spell from database
        try:
            from database import get_spell_by_name
            spell = get_spell_by_name(spell_name)
        except:
            spell = None
        
        if not spell:
            # Fallback to JSON library
            spells = SRDLibrary.search_srd("spells", spell_name, limit=1)
            if spells:
                spell = spells[0]
            else:
                spell = {
                    "name": spell_name.title(),
                    "level": "?",
                    "school": "Unknown",
                    "description": "No spell data available. Consider adding to SRD."
                }
        
        embed = discord.Embed(
            title=f"✨ {spell.get('name', spell_name).title()}",
            color=0x9B59B6
        )
        
        if "level" in spell:
            embed.add_field(name="Level", value=str(spell["level"]), inline=True)
        if "school" in spell:
            embed.add_field(name="School", value=spell["school"], inline=True)
        if "casting_time" in spell:
            embed.add_field(name="Casting Time", value=spell["casting_time"], inline=True)
        if "range" in spell:
            embed.add_field(name="Range", value=spell["range"], inline=True)
        if "components" in spell:
            embed.add_field(name="Components", value=spell["components"], inline=True)
        if "duration" in spell:
            embed.add_field(name="Duration", value=spell["duration"], inline=True)
        if "description" in spell:
            embed.description = str(spell["description"])[:1000]
        
        embed.set_footer(text="Local SRD • PHB 2024")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="monster", description="Look up a monster from SRD")
    async def monster_lookup(self, interaction: discord.Interaction, monster_name: str):
        """SRD monster lookup using database"""
        await interaction.response.defer()
        
        # Try to get monster from database
        try:
            from database import get_monster_by_name
            monster = get_monster_by_name(monster_name)
        except:
            monster = None
        
        if not monster:
            await interaction.followup.send(f"❌ Monster '{monster_name}' not found in SRD.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"👹 {monster.get('name', monster_name).title()}",
            color=0xE74C3C
        )
        
        if "type" in monster:
            embed.add_field(name="Type", value=monster["type"], inline=True)
        if "size" in monster:
            embed.add_field(name="Size", value=monster["size"], inline=True)
        if "alignment" in monster:
            embed.add_field(name="Alignment", value=monster["alignment"], inline=True)
        
        if "ac" in monster:
            embed.add_field(name="AC", value=str(monster["ac"]), inline=True)
        if "hp" in monster:
            embed.add_field(name="HP", value=str(monster["hp"]), inline=True)
        if "challenge_rating" in monster or "cr" in monster:
            cr = monster.get("challenge_rating") or monster.get("cr")
            embed.add_field(name="Challenge", value=str(cr), inline=True)
        
        # Ability scores
        abilities = []
        for ability in ["str", "dex", "con", "int", "wis", "cha"]:
            if ability in monster:
                abilities.append(f"{ability.upper()}: {monster[ability]}")
        if abilities:
            embed.add_field(name="Abilities", value=" • ".join(abilities), inline=False)
        
        if "description" in monster and monster["description"]:
            embed.description = str(monster["description"])[:500]
        
        embed.set_footer(text="Local SRD • MM 2024")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="damage_ref", description="Damage enemy by reference number")
    @app_commands.describe(ref="Enemy reference number", damage="Damage amount")
    async def damage_by_ref(self, interaction: discord.Interaction, ref: int, damage: int):
        """Damage using combat tracker abbreviation"""
        await interaction.response.defer()
        
        result = CombatTracker.apply_damage_by_ref(interaction.channel.id, ref, damage)
        
        if not result:
            await interaction.followup.send(f"No enemy with reference [{ref}]", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚔️ Damage Applied",
            color=0xE74C3C if damage > 0 else 0x2ECC71
        )
        
        if result.get("status") == "defeated":
            embed.description = f"**[{ref}] {result['name']}** defeated! (-{damage} HP)"
        else:
            embed.description = f"**[{ref}] {result['name']}**: {result['hp']}/{result['max_hp']} HP (-{damage})"
        
        if damage > 0 and result.get("conditions", "").lower().count("concentrating"):
            dc = max(10, damage // 2)
            embed.add_field(
                name="⚠️ Concentration Check",
                value=f"{result['name']} must make DC {dc} CON save",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="combat_status", description="Show compact combat status")
    async def combat_status(self, interaction: discord.Interaction):
        """Show optimized combat tracker"""
        await interaction.response.defer()
        
        summary = CombatTracker.get_combat_summary(interaction.channel.id)
        
        embed = discord.Embed(
            title="⚔️ Combat Status",
            description=summary,
            color=0xE74C3C
        )
        
        embed.add_field(
            name="Quick Commands",
            value="`/damage_ref [number] [amount]` - Damage enemy\n`/attack [ref]` - Attack enemy",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="session_report", description="Generate session summary")
    async def session_report(self, interaction: discord.Interaction):
        """Generate session scribe report"""
        await interaction.response.defer()
        
        summary = await HistoryManager.summarize_history(
            interaction.guild.id, 
            interaction.channel.id,
            force=True
        )
        
        embed = SessionScribe.generate_session_embed(
            interaction.guild.id,
            interaction.channel.id,
            "Session Report"
        )
        
        if embed:
            if summary:
                embed.add_field(name="📝 Summary", value=summary, inline=False)
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("No session data to report")
    
    @app_commands.command(name="check_destiny", description="Check destiny milestones")
    async def check_destiny(self, interaction: discord.Interaction):
        """Check destiny triggers"""
        await interaction.response.defer()
        
        triggers = DestinyManager.check_destiny_triggers(
            interaction.guild.id, 
            interaction.user.id
        )
        
        char = get_character(interaction.user.id, interaction.guild.id)
        if not char:
            await interaction.followup.send("No character found", ephemeral=True)
            return
        
        destiny_score = char.get('destiny_roll', 0)
        
        embed = discord.Embed(
            title="🔮 Destiny Check",
            color=0x9B59B6
        )
        
        embed.add_field(
            name="Your Destiny Score",
            value=f"**{destiny_score}** / 100",
            inline=True
        )
        
        next_milestone = None
        for threshold in sorted(DestinyManager.DESTINY_MILESTONES.keys()):
            if destiny_score < threshold:
                next_milestone = threshold
                break
        
        if next_milestone:
            embed.add_field(
                name="Next Milestone",
                value=f"{next_milestone} ({next_milestone - destiny_score} points away)",
                inline=True
            )
        
        if triggers:
            embed.add_field(
                name="🎉 New Milestones!",
                value="\n".join(triggers),
                inline=False
            )
        
        milestones = char.get('milestones', [])
        if milestones:
            achieved = [m.replace('milestone_', '') for m in milestones]
            embed.add_field(
                name="Achieved Milestones",
                value=f"Levels: {', '.join(achieved)}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="dm_suggest", description="Get AI suggestions for DM response")
    @app_commands.describe(player_action="The player's action to respond to")
    @app_commands.default_permissions(manage_guild=True)
    async def dm_suggest(self, interaction: discord.Interaction, player_action: str):
        """DM oversight mode"""
        await interaction.response.defer(ephemeral=True)
        
        history = HistoryManager.get_optimized_history(interaction.channel.id, limit=5)
        context = "\n".join([f"{role}: {content}" for role, content in history])
        
        suggestions = await DMOversight.suggest_outcome(
            interaction.guild.id,
            player_action,
            context
        )
        
        embed = discord.Embed(
            title="👻 DM Suggestions",
            description=f"For action: *{player_action[:100]}*",
            color=0x7289DA
        )
        
        options = suggestions.get("options", [])
        for i, option in enumerate(options[:3], 1):
            embed.add_field(
                name=f"Option {i}",
                value=option[:150],
                inline=False
            )
        
        recommended = suggestions.get("recommended", 0)
        embed.set_footer(text=f"Suggested: Option {recommended + 1}")
        
        class SuggestionView(discord.ui.View):
            def __init__(self, cog, options):
                super().__init__(timeout=60)
                self.cog = cog
                self.options = options
            
            @discord.ui.button(label="Use Option 1", style=discord.ButtonStyle.primary)
            async def use_option1(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[0]}")
                self.stop()
            
            @discord.ui.button(label="Use Option 2", style=discord.ButtonStyle.primary)
            async def use_option2(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[1]}")
                self.stop()
            
            @discord.ui.button(label="Use Option 3", style=discord.ButtonStyle.primary)
            async def use_option3(self, i: discord.Interaction, btn: discord.ui.Button):
                await i.response.send_message(f"**DM:** {self.options[2]}")
                self.stop()
        
        view = SuggestionView(self, options)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="summarize", description="Force history summarization")
    @app_commands.default_permissions(manage_guild=True)
    async def force_summarize(self, interaction: discord.Interaction):
        """Force history summarization"""
        await interaction.response.defer()
        
        summary = await HistoryManager.summarize_history(
            interaction.guild.id,
            interaction.channel.id,
            force=True
        )
        
        if summary:
            embed = discord.Embed(
                title="📚 History Summarized",
                description=summary,
                color=0x95A5A6
            )
            embed.set_footer(text="Old entries condensed to save memory")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Nothing to summarize")
    
    @app_commands.command(name="migrate_to_2024", description="Migrate campaign to 2024 rules")
    @app_commands.default_permissions(manage_guild=True)
    async def migrate_to_2024(self, interaction: discord.Interaction):
        """Migrate from legacy 2014 to 2024 rules"""
        await interaction.response.defer(ephemeral=True)
        
        update_dnd_rulebook(interaction.guild.id, "2024")
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id, guild_id, char_data FROM dnd_characters WHERE guild_id=?", (str(interaction.guild.id),))
        characters = c.fetchall()
        
        migrated = 0
        for uid, gid, char_json in characters:
            try:
                data = json.loads(char_json)
                
                if "race" in data:
                    data["species"] = data.pop("race")
                
                if "has_inspiration" in data:
                    data["heroic_inspiration"] = data.pop("has_inspiration")
                
                c.execute("UPDATE dnd_characters SET char_data=? WHERE user_id=? AND guild_id=?", 
                         (json.dumps(data), uid, gid))
                migrated += 1
                
            except Exception as e:
                print(f"Error migrating character {uid}: {e}")
        
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Migration Complete",
            description=f"Successfully migrated {migrated} characters to 2024 rules.",
            color=0x2ECC71
        )
        embed.add_field(name="Changes Applied", 
                       value="• 'Race' → 'Species'\n• 'Inspiration' → 'Heroic Inspiration'\n• Rulebook set to 2024", 
                       inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- GENERATIONAL VOID CYCLE COMMANDS ---
    
    @app_commands.command(name="mode_select", description="Choose Architect (auto) or Scribe (manual) mode")
    @app_commands.default_permissions(manage_guild=True)
    async def mode_select(self, interaction: discord.Interaction, mode: str = None):
        """Select session mode: Architect (Vespera controls tone/biome) or Scribe (players choose)"""
        await interaction.response.defer(ephemeral=True)
        
        # Create selection view if no mode specified
        if not mode:
            view = discord.ui.View()
            
            async def select_architect(interaction: discord.Interaction):
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.ARCHITECT)
                except:
                    # Table migration not complete yet, will work after restart
                    pass
                await interaction.response.send_message(
                    "✅ **Architect Mode Enabled**\n\nVespera now controls:\n"
                    "• Automatic tone shifting based on scene context\n"
                    "• Biome selection (random each session)\n"
                    "• All major narrative decisions",
                    ephemeral=True
                )
            
            async def select_scribe(interaction: discord.Interaction):
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.SCRIBE)
                except:
                    # Table migration not complete yet, will work after restart
                    pass
                await interaction.response.send_message(
                    "✅ **Scribe Mode Enabled**\n\nPlayers can:\n"
                    "• Select their starting biome from a menu\n"
                    "• Pick a persistent tone for the session\n"
                    "• Have more control over narrative direction",
                    ephemeral=True
                )
            
            architect_btn = discord.ui.Button(label="🏗️ Architect Mode", style=discord.ButtonStyle.primary)
            architect_btn.callback = select_architect
            view.add_item(architect_btn)
            
            scribe_btn = discord.ui.Button(label="📜 Scribe Mode", style=discord.ButtonStyle.secondary)
            scribe_btn.callback = select_scribe
            view.add_item(scribe_btn)
            
            embed = discord.Embed(
                title="⚙️ Session Mode Selection",
                description="Choose how you want to run your D&D campaign!",
                color=0x9B59B6
            )
            embed.add_field(
                name="🏗️ Architect Mode (Default DM)",
                value="Vespera manages the entire narrative:\n"
                      "• Auto biome selection\n"
                      "• Automatic tone shifting\n"
                      "• Full narrative control",
                inline=False
            )
            embed.add_field(
                name="📜 Scribe Mode (DM Assistant)",
                value="Players get manual overrides:\n"
                      "• Select starting biome from menu\n"
                      "• Pick persistent tone for session\n"
                      "• More narrative agency",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            # Direct mode selection
            if mode.lower() in ["architect", "arch"]:
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.ARCHITECT)
                except:
                    pass  # Table migration not complete yet
                await interaction.followup.send("✅ **Architect Mode** activated!", ephemeral=True)
            elif mode.lower() in ["scribe", "scr"]:
                try:
                    save_session_mode(interaction.guild.id, SessionModeManager.SCRIBE)
                except:
                    pass  # Table migration not complete yet
                await interaction.followup.send("✅ **Scribe Mode** activated!", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Unknown mode '{mode}'. Use: architect or scribe", ephemeral=True)
    
    @app_commands.command(name="chronicles", description="View campaign chronicles and victory scroll")
    @is_dnd_player()
    async def chronicles(self, interaction: discord.Interaction):
        """Display the Chronicles scroll with generational credits"""
        await interaction.response.defer()
        
        # Check if Phase 3 is complete
        phase, legends = get_dnd_campaign_data(interaction.guild.id)
        
        if phase < 3:
            await interaction.followup.send(
                f"⏳ Chronicles not yet available.\nCurrent Phase: {phase}/3\n\n"
                f"Complete Phase 3 to generate your campaign chronicles!",
                ephemeral=True
            )
            return
        
        # Get chronicles if they exist
        chronicle = get_chronicles(interaction.guild.id)
        
        if not chronicle:
            # Generate default chronicles if Phase 3 but no chronicle saved yet
            config = get_dnd_config(interaction.guild.id)
            party = json.loads(config[6]) if config and config[6] else []
            
            founder = "Unknown Founder"
            founder_id = "N/A"
            legend = "Unknown Legend"
            legend_id = "N/A"
            savior = "Unknown Savior"
            savior_id = "N/A"
            
            for user_id in party:
                if not str(user_id).startswith("npc_"):
                    char = get_character(user_id, interaction.guild.id)
                    if char:
                        if not founder or founder == "Unknown Founder":
                            founder = char.get('name', 'Unknown Founder')
                            founder_id = str(user_id)
                        elif not legend or legend == "Unknown Legend":
                            legend = char.get('name', 'Unknown Legend')
                            legend_id = str(user_id)
                        else:
                            savior = char.get('name', 'Unknown Savior')
                            savior_id = str(user_id)
            
            total_years = config[14] if config and len(config) > 14 else 0
            generations = max(1, total_years // 25)
            
            chronicle_data = {
                "campaign_name": config[3][:50] if config and config[3] else "Legacy Campaign",
                "phase_1_founder": founder,
                "phase_1_founder_id": founder_id,
                "phase_2_legend": legend,
                "phase_2_legend_id": legend_id,
                "phase_3_savior": savior,
                "phase_3_savior_id": savior_id,
                "total_years_elapsed": int(total_years),
                "total_generations": generations,
                "biome_name": config[1] if config else "The Void",
                "cycles_broken": 1,
                "eternal_guardians": [],
                "final_boss_name": "The Void Singularity"
            }
            
            save_chronicles(interaction.guild.id, chronicle_data)
            chronicle = get_chronicles(interaction.guild.id)
        
        # Build the Chronicles embed
        if chronicle:
            chronicle_id, campaign_name, founder, legend, savior, total_years, generations, biome, eternal_guardians, final_boss, victory_date = chronicle
            
            embed = discord.Embed(
                title="📜 THE CHRONICLES OF AGES PAST 📜",
                description=f"*A chronicle of the {total_years}-year saga across {generations} generations*",
                color=0xD4AF37
            )
            
            embed.add_field(
                name="⚔️ PHASE 1: THE FOUNDER",
                value=f"**{founder}** (The Conquest)\nFirst hero to face the void.",
                inline=False
            )
            
            embed.add_field(
                name="👑 PHASE 2: THE LEGEND",
                value=f"**{legend}** (The Transcendence)\n{total_years // 2} years after the Founder's deeds.",
                inline=False
            )
            
            embed.add_field(
                name="🌟 PHASE 3: THE SAVIOR",
                value=f"**{savior}** (The Legacy)\nDescendant who broke the cycle.",
                inline=False
            )
            
            embed.add_field(
                name="📍 REALM",
                value=f"The {biome}",
                inline=True
            )
            
            embed.add_field(
                name="⏳ TIME ELAPSED",
                value=f"{total_years} years\n{generations} generations",
                inline=True
            )
            
            embed.add_field(
                name="🏆 FINAL VICTORY",
                value=f"Defeated: **{final_boss}**",
                inline=True
            )
            
            if eternal_guardians:
                try:
                    guardians = json.loads(eternal_guardians)
                    if guardians:
                        embed.add_field(
                            name="🛡️ ETERNAL GUARDIANS",
                            value=", ".join(guardians[:5]),
                            inline=False
                        )
                except:
                    pass
            
            embed.set_footer(text="Thus ends the chronicle of the Void Cycle")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "❌ Chronicles not yet generated.\n\n"
                "Defeat the final Phase 3 boss to create your campaign's eternal chronicle!",
                ephemeral=True
            )
    
    # --- EVENT LISTENERS ---
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-rule lookup on spell mentions"""
        if message.author.bot or not message.guild:
            return
        
        if not isinstance(message.channel, discord.Thread):
            return
        
        spell_pattern = r'(?:cast|use|prepares?)\s+([a-zA-Z\s]+)(?:spell)?'
        matches = re.findall(spell_pattern, message.content.lower())
        
        for match in matches:
            spell_name = match.strip()
            if len(spell_name) > 3:
                rules = RulebookRAG.lookup_rule(spell_name, limit=1)
                if rules:
                    rule_name, rule_text = rules[0]
                    
                    embed = discord.Embed(
                        title=f"📖 {rule_name.title()}",
                        description=rule_text[:250] + "...",
                        color=0x3498DB
                    )
                    embed.set_footer(text="Auto-rule lookup • Use /rule for full text")
                    
                    await message.reply(embed=embed, mention_author=False)
                    break
    
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Auto-summarize after many commands"""
        if not isinstance(ctx.channel, discord.Thread):
            return
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM dnd_history WHERE thread_id=?", (str(ctx.channel.id),))
        count = c.fetchone()[0]
        conn.close()
        
        if count >= 30 and count % 15 == 0:
            await HistoryManager.summarize_history(ctx.guild.id, ctx.channel.id)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Auto-join voice when players join during active session"""
        if member.bot or not after.channel:
            return
        
        try:
            config = get_dnd_config(member.guild.id)
            if not config or not config[2] or config[2] == "New Campaign Started.":
                return
            
            guild_vc = member.guild.voice_client
            if guild_vc and guild_vc.is_connected():
                return
            
            try:
                vc = await after.channel.connect()
                self.voice_clients[member.guild.id] = vc
                
                current_loc = config[1] or 'tavern'
                audio_file = f"{AUDIO_PATH}{current_loc}.ogg"
                if os.path.exists(audio_file):
                    if vc.is_playing():
                        vc.stop()
                    vc.play(discord.FFmpegPCMAudio(audio_file))
            except Exception as e:
                print(f"[DND] Voice connect error: {e}")
                
        except Exception as e:
            print(f"[DND] Voice state error: {e}")

async def setup(bot):
    """Setup function for the cog"""
    RulebookRAG.init_rulebook_table()
    
    os.makedirs("./srd", exist_ok=True)
    
    srd_path = "./srd/spells.json"
    if not os.path.exists(srd_path):
        minimal_srd = {
            "fireball": {
                "name": "Fireball",
                "level": 3,
                "school": "Evocation",
                "casting_time": "1 action",
                "range": "150 feet",
                "components": "V, S, M (a tiny ball of bat guano and sulfur)",
                "duration": "Instantaneous",
                "description": "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one. The fire spreads around corners. It ignites flammable objects in the area that aren't being worn or carried."
            },
            "cure_wounds": {
                "name": "Cure Wounds",
                "level": 1,
                "school": "Evocation",
                "casting_time": "1 action",
                "range": "Touch",
                "components": "V, S",
                "duration": "Instantaneous",
                "description": "A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier. This spell has no effect on undead or constructs."
            }
        }
        
        with open(srd_path, 'w', encoding='utf-8') as f:
            json.dump(minimal_srd, f, indent=2)
    
    await bot.add_cog(DNDCog(bot))
# --- END OF FILE dnd_cog.py ---