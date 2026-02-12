#!/usr/bin/env python3
"""
SRD 2024 Importer Script
Imports D&D 5e 2024 SRD data (spells, monsters, weapons) into SQLite database.
Optimized for 1GB VPS with batch insertion and sanitization.
"""

import sqlite3
import json
import os
import sys
import re
from typing import List, Dict, Tuple, Optional

# Database path
DB_FILE = os.path.abspath("bot_database.db")
SRD_PATH = "./srd"

# Trademarked terms to sanitize (2024 SRD compliance)
TRADEMARKS_TO_REMOVE = {
    "deck of many things": "mysterious deck",
    "forgotten realms": "known world",
    "wizards of the coast": "publishers",
}

class SRDImporter:
    """Efficient SRD 2024 importer with batch processing"""
    
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def sanitize_text(self, text: str) -> str:
        """Remove trademarked terms per SRD compliance"""
        if not text:
            return text
        
        result = text.lower()
        for trademark, replacement in TRADEMARKS_TO_REMOVE.items():
            result = result.replace(trademark, replacement)
        
        return result
    
    def load_json_safe(self, filepath: str) -> Optional[List[Dict]]:
        """Safely load JSON file with error handling"""
        if not os.path.exists(filepath):
            print(f"⚠️ File not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    print(f"⚠️ Invalid JSON structure in {filepath} (expected list)")
                    return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error in {filepath}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error loading {filepath}: {e}")
            return None
    
    def import_spells(self, batch_size: int = 100) -> int:
        """
        Import spells from spells.json using batch insertion.
        Returns count of spells imported.
        """
        print("\n📚 Importing D&D 2024 Spells...")
        
        spells_file = os.path.join(SRD_PATH, "spells.json")
        spells_data = self.load_json_safe(spells_file)
        
        if not spells_data:
            print("❌ Failed to load spells data")
            return 0
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Prepare batch for insertion
        spell_records = []
        imported_count = 0
        
        for spell in spells_data:
            try:
                spell_id = spell.get('name', '').lower().replace(' ', '_')
                name = spell.get('name', 'Unknown')
                level = spell.get('level', 0)
                school = spell.get('school', 'universal')
                classes = json.dumps(spell.get('classes', []))
                casting_time = spell.get('actionType', 'action')
                range_val = spell.get('range', 'Self')
                components = json.dumps(spell.get('components', []))
                duration = spell.get('duration', 'Instantaneous')
                concentration = 1 if spell.get('concentration', False) else 0
                ritual = 1 if spell.get('ritual', False) else 0
                description = self.sanitize_text(spell.get('description', ''))
                
                # Extract damage from cantripUpgrade or description
                damage = spell.get('cantripUpgrade', '')
                
                spell_records.append((
                    spell_id, name, level, school, classes, casting_time,
                    range_val, components, duration, concentration, ritual,
                    description, damage, 'PHB 2024'
                ))
                
                # Batch insert every N records
                if len(spell_records) >= batch_size:
                    cursor.executemany(
                        '''INSERT OR REPLACE INTO srd_spells 
                           (spell_id, name, level, school, classes, casting_time, range, 
                            components, duration, concentration, ritual, description, damage, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        spell_records
                    )
                    imported_count += len(spell_records)
                    print(f"  ✓ Inserted batch: {imported_count} spells processed")
                    spell_records = []
            
            except Exception as e:
                print(f"  ⚠️ Skipped spell '{spell.get('name', 'Unknown')}': {e}")
                continue
        
        # Insert remaining records
        if spell_records:
            cursor.executemany(
                '''INSERT OR REPLACE INTO srd_spells 
                   (spell_id, name, level, school, classes, casting_time, range, 
                    components, duration, concentration, ritual, description, damage, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                spell_records
            )
            imported_count += len(spell_records)
        
        conn.commit()
        print(f"✅ Successfully imported {imported_count} spells!")
        return imported_count
    
    def import_monsters(self, batch_size: int = 100) -> int:
        """
        Import monsters from monsters.json using batch insertion.
        Returns count of monsters imported.
        """
        print("\n👹 Importing D&D 2024 Monsters...")
        
        monsters_file = os.path.join(SRD_PATH, "monsters.json")
        monsters_data = self.load_json_safe(monsters_file)
        
        if not monsters_data:
            print("❌ Failed to load monsters data")
            return 0
        
        conn = self.connect()
        cursor = conn.cursor()
        
        monster_records = []
        imported_count = 0
        
        for monster in monsters_data:
            try:
                monster_id = monster.get('name', '').lower().replace(' ', '_')
                name = monster.get('name', 'Unknown')
                
                # Extract properties safely
                props = monster.get('properties', {})
                monster_type = props.get('Type', 'humanoid')
                size = props.get('Size', 'Medium')
                alignment = props.get('Alignment', 'Unaligned')
                ac = props.get('AC', 10)
                hp = props.get('HP', 1)
                
                # Ability scores (2024 rules use new base)
                str_score = int(props.get('STR', 10))
                dex_score = int(props.get('DEX', 10))
                con_score = int(props.get('CON', 10))
                int_score = int(props.get('INT', 10))
                wis_score = int(props.get('WIS', 10))
                cha_score = int(props.get('CHA', 10))
                
                cr = props.get('Challenge Rating', 0)
                description = self.sanitize_text(monster.get('description', ''))
                
                # Store JSON traits and actions
                traits = json.dumps(props.get('data-Traits', []))
                actions = json.dumps(props.get('data-Actions', []))
                
                monster_records.append((
                    monster_id, name, monster_type, size, alignment, ac, hp,
                    str_score, dex_score, con_score, int_score, wis_score, cha_score,
                    cr, description, traits, actions, 'MM 2024'
                ))
                
                if len(monster_records) >= batch_size:
                    cursor.executemany(
                        '''INSERT OR REPLACE INTO srd_monsters 
                           (monster_id, name, type, size, alignment, ac, hp, str, dex, con, 
                            int, wis, cha, challenge_rating, description, traits, actions, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        monster_records
                    )
                    imported_count += len(monster_records)
                    print(f"  ✓ Inserted batch: {imported_count} monsters processed")
                    monster_records = []
            
            except Exception as e:
                print(f"  ⚠️ Skipped monster '{monster.get('name', 'Unknown')}': {e}")
                continue
        
        if monster_records:
            cursor.executemany(
                '''INSERT OR REPLACE INTO srd_monsters 
                   (monster_id, name, type, size, alignment, ac, hp, str, dex, con, 
                    int, wis, cha, challenge_rating, description, traits, actions, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                monster_records
            )
            imported_count += len(monster_records)
        
        conn.commit()
        print(f"✅ Successfully imported {imported_count} monsters!")
        return imported_count
    
    def import_weapons_2024(self) -> int:
        """
        Import 2024 weapon mastery mapping.
        Manually curated based on 2024 PHB weapon list.
        """
        print("\n⚔️ Importing 2024 Weapon Mastery Mapping...")
        
        # 2024 PHB Weapons with Mastery Properties
        weapons_2024 = [
            # Simple Melee Weapons
            ("club", "Club", "simple_melee", "Sap", "1d4", "5", "Light"),
            ("dagger", "Dagger", "simple_melee", "Finesse", "1d4", "20/60", "Finesse, Light, Thrown"),
            ("greatclub", "Greatclub", "simple_melee", "Sap", "1d8", "5", "Two-Handed"),
            ("handaxe", "Handaxe", "simple_melee", "Vex", "1d6", "20/60", "Light, Thrown"),
            ("javelin", "Javelin", "simple_melee", "Slow", "1d6", "30/120", "Melee, Thrown"),
            ("mace", "Mace", "simple_melee", "Sap", "1d6", "5", ""),
            ("quarterstaff", "Quarterstaff", "simple_melee", "Polearm", "1d6/1d8", "5", "Versatile"),
            ("sickle", "Sickle", "simple_melee", "Nick", "1d4", "5", "Light"),
            ("spear", "Spear", "simple_melee", "Polearm", "1d6/1d8", "20/60", "Melee, Thrown, Versatile"),
            
            # Martial Melee Weapons
            ("battleaxe", "Battleaxe", "martial_melee", "Cleave", "1d8/1d10", "5", "Versatile"),
            ("flail", "Flail", "martial_melee", "Sap", "1d8", "5", ""),
            ("glaive", "Glaive", "martial_melee", "Polearm", "1d10", "5", "Heavy, Reach, Two-Handed"),
            ("greataxe", "Greataxe", "martial_melee", "Cleave", "1d12", "5", "Heavy, Two-Handed"),
            ("greatsword", "Greatsword", "martial_melee", "Cleave", "2d6", "5", "Heavy, Two-Handed"),
            ("halberd", "Halberd", "martial_melee", "Polearm", "1d10", "5", "Heavy, Reach, Two-Handed"),
            ("lance", "Lance", "martial_melee", "Cleave", "1d12", "5", "Reach, Two-Handed"),
            ("longsword", "Longsword", "martial_melee", "Sap", "1d8/1d10", "5", "Versatile"),
            ("maul", "Maul", "martial_melee", "Sap", "2d6", "5", "Heavy, Two-Handed"),
            ("morningstar", "Morningstar", "martial_melee", "Sap", "1d8", "5", ""),
            ("pike", "Pike", "martial_melee", "Polearm", "1d10", "5", "Heavy, Reach, Two-Handed"),
            ("rapier", "Rapier", "martial_melee", "Finesse", "1d8", "5", "Finesse"),
            ("scimitar", "Scimitar", "martial_melee", "Nick", "1d6", "5", "Finesse, Light"),
            ("shortsword", "Shortsword", "martial_melee", "Finesse", "1d6", "5", "Finesse, Light"),
            ("trident", "Trident", "martial_melee", "Polearm", "1d6/1d8", "20/60", "Melee, Thrown, Versatile"),
            ("warpick", "War Pick", "martial_melee", "Vex", "1d8", "5", ""),
            ("warhammer", "Warhammer", "martial_melee", "Sap", "1d8/1d10", "5", "Versatile"),
            ("whip", "Whip", "martial_melee", "Nick", "1d4", "5", "Finesse, Reach"),
            
            # Simple Ranged Weapons
            ("dart", "Dart", "simple_ranged", "Finesse", "1d4", "20/60", "Finesse, Thrown"),
            ("shortbow", "Shortbow", "simple_ranged", "Nick", "1d6", "80/320", "Two-Handed"),
            ("sling", "Sling", "simple_ranged", "Slow", "1d4", "30/120", ""),
            
            # Martial Ranged Weapons
            ("blowgun", "Blowgun", "martial_ranged", "Slow", "1", "25/100", ""),
            ("hand_crossbow", "Hand Crossbow", "martial_ranged", "Vex", "1d6", "30/120", "Light, Loading"),
            ("heavy_crossbow", "Heavy Crossbow", "martial_ranged", "Slow", "1d10", "100/400", "Heavy, Loading, Two-Handed"),
            ("longbow", "Longbow", "martial_ranged", "Slow", "1d8", "150/600", "Heavy, Two-Handed"),
        ]
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Batch insert weapons
        cursor.executemany(
            '''INSERT OR REPLACE INTO weapon_mastery 
               (weapon_id, name, weapon_type, mastery_property, dice_damage, range, properties, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [(wid, name, wtype, mastery, damage, rng, props, 'PHB 2024') 
             for wid, name, wtype, mastery, damage, rng, props in weapons_2024]
        )
        
        conn.commit()
        print(f"✅ Successfully imported {len(weapons_2024)} weapons with mastery properties!")
        return len(weapons_2024)
    
    def import_all(self) -> Dict[str, int]:
        """Import all SRD data"""
        print("=" * 60)
        print("🎲 D&D 5e 2024 SRD Importer")
        print("=" * 60)
        
        results = {}
        
        try:
            results['spells'] = self.import_spells()
            results['monsters'] = self.import_monsters()
            results['weapons'] = self.import_weapons_2024()
            
            print("\n" + "=" * 60)
            print("📊 Import Summary")
            print("=" * 60)
            print(f"  ✓ Spells imported: {results['spells']}")
            print(f"  ✓ Monsters imported: {results['monsters']}")
            print(f"  ✓ Weapons imported: {results['weapons']}")
            print(f"  ✓ Total records: {sum(results.values())}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Import failed: {e}")
            results['error'] = str(e)
        
        finally:
            self.close()
        
        return results


if __name__ == "__main__":
    importer = SRDImporter()
    results = importer.import_all()
    
    # Exit with error code if import failed
    if 'error' in results:
        sys.exit(1)
