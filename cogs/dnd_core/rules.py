import sqlite3
import re
import time
import os
import sys
import json
from typing import List, Dict, Tuple, Optional

# Ensure we can import from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import DB_FILE

class ActionEconomyValidator:
    """
    Validate and limit player actions to D&D 5e/2024 rules.
    Players have: Action, Bonus Action, Reaction, Movement.
    """
    
    ACTION_KEYWORDS = {
        "action": [
            "attack", "cast", "dodge", "disengage", "dash", "ready",
            "hide", "search", "use", "drink", "disarm", "help", "push",
            "shove", "grapple", "sheathe", "draw", "reload"
        ],
        "bonus_action": [
            "bonus", "quick cast", "quicken", "action surge", "flurry",
            "cunning action", "second wind", "hunter's mark", "bonus spell",
            "offhand attack", "off-hand", "dual wield", "bonus attack"
        ],
        "reaction": [
            "reaction", "counter", "counterspell", "shield", "opportunity",
            "opportunity attack", "reaction attack", "riposte", "parry",
            "readied action"
        ],
        "movement": [
            "move", "walk", "run", "fly", "swim", "step",
            "dash", "jump", "teleport", "stride"
        ]
    }
    
    _last_db_refresh = None
    _refresh_interval = 3600
    
    MULTIPLE_ACTION_INDICATORS = [
        " and ", " then ", " after that ", " next ", " before ", 
        " while ", " also ", " plus ", ", then", ". then",
    ]
    
    ROLEPLAY_EXCEPTIONS = [
        "look at", "walk over and look", "move to", "walk to",
        "run to", "approach and examine", "move closer and inspect",
        "step toward", "go to", "head to", "walk around",
        "move and see", "walk and observe", "go and check"
    ]
    
    @staticmethod
    def refresh_from_database():
        now = time.time()
        if ActionEconomyValidator._last_db_refresh is not None:
            if now - ActionEconomyValidator._last_db_refresh < ActionEconomyValidator._refresh_interval:
                return
        
        try:
            action_keywords = RulebookIngestor.get_action_keywords()
            if action_keywords:
                current_actions = set(ActionEconomyValidator.ACTION_KEYWORDS["action"])
                new_actions = set(action_keywords)
                merged = current_actions.union(new_actions)
                ActionEconomyValidator.ACTION_KEYWORDS["action"] = list(merged)
                ActionEconomyValidator._last_db_refresh = now
        except Exception as e:
            print(f"[ActionEconomyValidator] DB refresh failed: {e}")
    
    @staticmethod
    def validate_action_economy(action: str, character_data: dict = None) -> dict:
        ActionEconomyValidator.refresh_from_database()
        action_lower = action.lower()
        is_roleplay_only = any(exception in action_lower for exception in ActionEconomyValidator.ROLEPLAY_EXCEPTIONS)
        
        extra_attacks = 1
        if character_data:
            char_level = character_data.get('level', 1)
            char_class = character_data.get('class', '').lower()
            if char_class in ['fighter', 'paladin', 'ranger', 'barbarian', 'monk']:
                if char_level >= 5: extra_attacks = 2
                if char_class == 'fighter' and char_level >= 11: extra_attacks = 3
                if char_class == 'fighter' and char_level >= 20: extra_attacks = 4
            conditions = character_data.get('conditions', '')
            if 'haste' in conditions.lower():
                extra_attacks += 1
        
        action_count = 0
        bonus_action_count = 0
        reaction_count = 0
        movement_mentioned = False
        attack_instances = 0
        
        for keyword in ActionEconomyValidator.ACTION_KEYWORDS['action']:
            if keyword in action_lower:
                if keyword in ['attack', 'strike', 'hit', 'slash', 'shoot']:
                    attack_instances += 1
                else:
                    action_count += 1
        
        if attack_instances > 0:
            if attack_instances <= extra_attacks:
                action_count += 1
            else:
                action_count += attack_instances
        
        for keyword in ActionEconomyValidator.ACTION_KEYWORDS['bonus_action']:
            if keyword in action_lower: bonus_action_count += 1
            
        for keyword in ActionEconomyValidator.ACTION_KEYWORDS['reaction']:
            if keyword in action_lower: reaction_count += 1
            
        for keyword in ActionEconomyValidator.ACTION_KEYWORDS['movement']:
            if keyword in action_lower: 
                movement_mentioned = True
                break
        
        if not is_roleplay_only:
            multiple_actions_connectors = 0
            for indicator in ActionEconomyValidator.MULTIPLE_ACTION_INDICATORS:
                if indicator in action_lower: multiple_actions_connectors += 1
            
            if multiple_actions_connectors > 0 and action_count <= 1 and bonus_action_count == 0 and reaction_count == 0:
                pass
            elif multiple_actions_connectors > 0 and not movement_mentioned:
                action_count = max(action_count, multiple_actions_connectors + 1)
        
        is_valid = True
        excess_actions = []
        warning = ""
        enforcement_instruction = ""
        
        if action_count > 1:
            is_valid = False
            excess_actions.append(f"Multiple Actions ({action_count} attempted, max 1)")
            if attack_instances > extra_attacks:
                warning = f"⚠️ OVERFLOW: Player attempted {attack_instances} attacks but Extra Attack allows {extra_attacks}."
                enforcement_instruction = f"Allow first {extra_attacks} attacks only."
            else:
                warning = f"⚠️ OVERFLOW: Attempted {action_count} actions."
                enforcement_instruction = "Only the FIRST action succeeds."
        
        if bonus_action_count > 1:
            is_valid = False
            excess_actions.append(f"Multiple Bonus Actions ({bonus_action_count} max 1)")
            warning = f"⚠️ OVERFLOW: {bonus_action_count} bonus actions."
            enforcement_instruction = "Only FIRST bonus action succeeds."
            
        if reaction_count > 1:
            is_valid = False
            excess_actions.append(f"Multiple Reactions")
            warning = "⚠️ OVERFLOW: Multiple reactions."
            
        if (action_count + bonus_action_count) > 2:
             if "first" not in enforcement_instruction.lower():
                is_valid = False
                enforcement_instruction = "Player attempted too much. Enforce action economy."

        if action_count == 0 and bonus_action_count == 0 and len(action) > 20:
             enforcement_instruction = "General roleplay. Resolve naturally."

        return {
            'action_count': action_count,
            'bonus_action_count': bonus_action_count,
            'reaction_count': reaction_count,
            'is_valid': is_valid,
            'excess_actions': excess_actions,
            'warning': warning,
            'enforcement_instruction': enforcement_instruction
        }

class RulebookIngestor:
    HEADER_PATTERN = re.compile(r'^####\s+(.+?)(?:\s+\[(.+?)\])?\s*$')
    SEE_ALSO_PATTERN = re.compile(r'\*See also\*\s+[""](.+?)[""]', re.IGNORECASE)
    BATCH_SIZE = 50
    
    @staticmethod
    def ingest_markdown_rulebook(file_path: str, source: str = "SRD 2024") -> Dict[str, int]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Rulebook not found: {file_path}")
        
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0}
        batch = []
        current_keyword = None
        current_rule_type = None
        current_text_lines = []
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip()
                    match = RulebookIngestor.HEADER_PATTERN.match(line)
                    if match:
                        if current_keyword and current_text_lines:
                            batch.append(RulebookIngestor._create_entry(current_keyword, current_rule_type, current_text_lines, source))
                            if len(batch) >= RulebookIngestor.BATCH_SIZE:
                                RulebookIngestor._batch_insert(c, batch, stats)
                                batch = []
                        current_keyword = match.group(1).strip()
                        current_rule_type = match.group(2).strip() if match.group(2) else "general"
                        current_text_lines = []
                    elif current_keyword:
                        if not current_text_lines and not line.strip(): continue
                        if line.startswith('## ') or line.startswith('# '):
                            if current_text_lines:
                                batch.append(RulebookIngestor._create_entry(current_keyword, current_rule_type, current_text_lines, source))
                            current_keyword = None
                            current_text_lines = []
                        else:
                            current_text_lines.append(line)
                if current_keyword and current_text_lines:
                    batch.append(RulebookIngestor._create_entry(current_keyword, current_rule_type, current_text_lines, source))
                if batch:
                    RulebookIngestor._batch_insert(c, batch, stats)
            conn.commit()
            RulebookRAG.RULE_CACHE.clear()
        finally:
            conn.close()
        return stats

    @staticmethod
    def _create_entry(keyword, rule_type, text_lines, source):
        return (keyword.lower(), '\n'.join(text_lines).strip(), rule_type.lower() if rule_type != "general" else "general", source)
    
    @staticmethod
    def _batch_insert(cursor, batch, stats):
        try:
            cursor.executemany("INSERT OR REPLACE INTO dnd_rulebook (keyword, rule_text, rule_type, source) VALUES (?, ?, ?, ?)", batch)
            stats['inserted'] += len(batch)
        except sqlite3.Error:
            for entry in batch:
                try:
                    cursor.execute("INSERT OR REPLACE INTO dnd_rulebook (keyword, rule_text, rule_type, source) VALUES (?, ?, ?, ?)", entry)
                    stats['inserted'] += 1
                except: stats['skipped'] += 1

    @staticmethod
    def extract_see_also_references(keyword: str) -> List[str]:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT rule_text FROM dnd_rulebook WHERE keyword = ?", (keyword.lower(),))
        result = c.fetchone()
        conn.close()
        if not result: return []
        matches = RulebookIngestor.SEE_ALSO_PATTERN.findall(result[0])
        refs = []
        for match in matches:
             for part in re.split(r',|and|;', match):
                 clean = part.strip().strip('"').strip("'").strip()
                 if clean: refs.append(clean.lower())
        return refs

    @staticmethod
    def get_action_keywords() -> List[str]:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("SELECT keyword FROM dnd_rulebook WHERE rule_type = 'action'")
            return [row[0] for row in c.fetchall()]
        except: return []
        finally: conn.close()

class RulebookRAG:
    RULE_CACHE = {}
    CACHE_MAX_SIZE = 50
    
    @staticmethod
    def init_rulebook_table():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS dnd_rulebook (keyword TEXT PRIMARY KEY, rule_text TEXT, rule_type TEXT, source TEXT)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_rulebook_keyword ON dnd_rulebook(keyword)''')
        c.execute("SELECT COUNT(*) FROM dnd_rulebook")
        if c.fetchone()[0] == 0:
             # Basic seeds
             pass
        conn.commit()
        conn.close()

    @staticmethod
    def lookup_rule(keyword: str, limit: int = 3, require_precision: bool = False, follow_see_also: bool = False) -> List[Tuple[str, str]]:
        keyword_clean = keyword.lower().strip()
        cache_key = f"{keyword_clean}_p{require_precision}_s{follow_see_also}"
        if cache_key in RulebookRAG.RULE_CACHE: return RulebookRAG.RULE_CACHE[cache_key]
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        if require_precision or "mechanics" in keyword_clean:
             query = '''SELECT keyword, rule_text FROM dnd_rulebook 
                        WHERE keyword LIKE ? OR rule_text LIKE ?
                        LIMIT ?'''
             c.execute(query, (f"%{keyword_clean}%", f"%{keyword_clean}%", limit))
        else:
             c.execute('''SELECT keyword, rule_text FROM dnd_rulebook 
                        WHERE keyword LIKE ? OR rule_text LIKE ? LIMIT ?''', 
                        (f"%{keyword_clean}%", f"%{keyword_clean}%", limit))
        
        results = c.fetchall()
        conn.close()
        
        if len(RulebookRAG.RULE_CACHE) >= RulebookRAG.CACHE_MAX_SIZE:
            RulebookRAG.RULE_CACHE.pop(next(iter(RulebookRAG.RULE_CACHE)))
        RulebookRAG.RULE_CACHE[cache_key] = results
        return results

    @staticmethod
    def add_rule(keyword: str, rule_text: str, rule_type: str = "custom", source: str = "DM"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO dnd_rulebook VALUES (?, ?, ?, ?)", (keyword.lower(), rule_text, rule_type, source))
        conn.commit()
        conn.close()
        RulebookRAG.RULE_CACHE[keyword.lower()] = [(keyword, rule_text)]

class SRDLibrary:
    SRD_CACHE = {}
    @staticmethod
    def load_srd_data(category: str) -> dict:
        if category in SRDLibrary.SRD_CACHE: return SRDLibrary.SRD_CACHE[category]
        srd_path = f"./srd/{category}.json"
        if os.path.exists(srd_path):
            try:
                with open(srd_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    SRDLibrary.SRD_CACHE[category] = data
                    return data
            except: pass
        return {}
    
    @staticmethod
    def search_srd(category: str, query: str, limit: int = 5) -> list:
        data = SRDLibrary.load_srd_data(category)
        results = []
        for key, item in data.items():
            if query.lower() in key.lower() or query.lower() in item.get('name', '').lower():
                results.append(item)
                if len(results) >= limit: break
        return results
