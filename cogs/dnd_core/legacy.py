import sqlite3
import time
import random
from typing import Optional, List, Tuple, Dict
from database import DB_FILE, get_character, update_character

# --- LEGACY ITEM HAND-ME-DOWNS SYSTEM ---
class LegacyVaultSystem:
    """
    Manage legacy item hand-me-downs across character generations.
    Phase 1: Player selects an item at campaign end.
    Phase 3: Descendant finds it void-scarred (enhanced + corruption drawback).
    """
    
    @staticmethod
    def create_legacy_vault_table():
        """Ensure legacy_vault table exists in database"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS legacy_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            character_name TEXT,
            generation INTEGER DEFAULT 1,
            item_name TEXT NOT NULL,
            item_description TEXT,
            owner TEXT,
            phase_locked INTEGER,
            is_void_scarred INTEGER DEFAULT 0,
            scarring_effect TEXT,
            corruption_drawback TEXT,
            discovered_phase INTEGER,
            created_at REAL,
            discovered_at REAL
        )''')
        
        c.execute('''CREATE INDEX IF NOT EXISTS idx_legacy_vault_char 
                    ON legacy_vault(guild_id, character_id)''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_legacy_item(guild_id: int, character_id: str, character_name: str, 
                       generation: int, item_name: str, item_description: str, owner: str) -> bool:
        """
        Store an item in the legacy vault at end of Phase 1.
        """
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            c.execute('''INSERT INTO legacy_vault 
                        (guild_id, character_id, character_name, generation, item_name, 
                         item_description, owner, phase_locked, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (str(guild_id), str(character_id), character_name, generation,
                      item_name, item_description, owner, generation, time.time()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[LegacyVault] Error storing item: {e}")
            return False
    
    @staticmethod
    def discover_legacy_items(guild_id: int, character_id: str, current_generation: int) -> list:
        """
        Retrieve and void-scar legacy items for descendant (Phase 3).
        Void-scarring adds a powerful buff but introduces a corruption drawback.
        """
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Fetch all items passed down from ancestors
            c.execute('''SELECT id, item_name, item_description, owner, generation 
                        FROM legacy_vault 
                        WHERE guild_id = ? AND is_void_scarred = 0 
                        AND generation < ?''',
                     (str(guild_id), current_generation))
            
            items = c.fetchall()
            discovered = []
            
            # Apply void-scarring to each item
            for item_id, item_name, item_desc, owner, gen in items:
                scarring_effect, corruption = LegacyVaultSystem._generate_void_scarring(item_name, owner)
                
                c.execute('''UPDATE legacy_vault 
                            SET is_void_scarred = 1, scarring_effect = ?, 
                                corruption_drawback = ?, discovered_phase = ?, discovered_at = ?
                            WHERE id = ?''',
                         (scarring_effect, corruption, current_generation, time.time(), item_id))
                
                discovered.append({
                    "item_name": item_name,
                    "original_owner": owner,
                    "original_description": item_desc,
                    "scarring_effect": scarring_effect,
                    "corruption_drawback": corruption,
                    "lore": f"This item once belonged to {owner} (Generation {gen}). The void has marked it with power and curse."
                })
            
            conn.commit()
            conn.close()
            
            return discovered
            
        except Exception as e:
            print(f"[LegacyVault] Error discovering items: {e}")
            return []
    
    @staticmethod
    def _generate_void_scarring(item_name: str, owner: str) -> tuple:
        """
        Generate void-scarring effects (buff + corruption).
        Returns: (scarring_effect, corruption_drawback)
        """
        scarring_buffs = [
            "+1 to attack rolls and damage rolls",
            "Resistance to one damage type of your choice",
            "Once per day: Gain advantage on a saving throw",
            "Emits dim light in a 10-foot radius",
            "Once per long rest: Deal an extra 1d6 force damage on a hit",
            "Advantage on checks to resist being charmed or frightened",
        ]
        
        corruption_drawbacks = [
            "Once per day, you must make a WIS save (DC 12) or act aggressive toward nearest creature",
            "Disadvantage on Wisdom (Insight) checks about the void or its origins",
            "Once per long rest, you experience a haunting dream about the void",
            "Disadvantage on saving throws against necrotic damage",
            "You cannot speak lies about the item's void-scarred nature",
            "Once per day, the item whispers in your mind for 1 minute (distracting)",
        ]
        
        buff = random.choice(scarring_buffs)
        corruption = random.choice(corruption_drawbacks)
        
        return buff, corruption

class SoulRemnantManager:
    """
    Manages corrupted echoes of Phase 1/2 ancestors appearing in Phase 3.
    """
    
    @staticmethod
    def create_soul_remnant(ancestor_name: str, ancestor_class: str, 
                          ancestor_destiny_score: int, phase: int) -> dict:
        """
        Create a corrupted mini-boss from an ancestor's data.
        """
        # Scale stats based on destiny score (higher = more powerful echo)
        base_hp = 50 + (ancestor_destiny_score // 10) * 10
        ac = 12 + (ancestor_destiny_score // 25)
        damage_die = "1d8" if ancestor_destiny_score < 50 else "1d10"
        
        return {
            "name": f"Echo of {ancestor_name}",
            "type": "Soul Remnant",
            "hp": base_hp,
            "max_hp": base_hp,
            "ac": ac,
            "damage_die": damage_die,
            "original_class": ancestor_class,
            "original_destiny": ancestor_destiny_score,
            "corruption_level": min(100, 30 + (ancestor_destiny_score // 2)),
            "special_move": f"Spectral {ancestor_class} Technique",
            "description": f"A twisted echo of a legendary {ancestor_class} from {phase} generations past",
            "defeated": False
        }
    
    @staticmethod
    def get_encounter_narrative(remnant: dict) -> str:
        """Generate atmospheric narration for soul remnant encounter"""
        corruption = remnant["corruption_level"]
        return (
            f"Before you materializes a spectral form... {remnant['name']}.\n"
            f"Their essence is twisted and corrupted, barely recognizable after "
            f"centuries of void influence. The air grows cold as they turn to face you.\n"
            f"**Corruption Level: {corruption}%** - They are barely themselves anymore."
        )

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
        return "No legacy buff"
