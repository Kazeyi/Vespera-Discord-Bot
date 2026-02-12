#!/usr/bin/env python3
"""
Quick SRD Setup Guide
Run this script ONCE to initialize the SRD database
"""

import subprocess
import sys
import os
from database import DatabaseManager

def main():
    print("=" * 70)
    print("🎲 D&D 5e 2024 SRD - Quick Setup Guide")
    print("=" * 70)
    
    # STEP 0: Initialize database schema
    print("\n⚙️  STEP 0: Initialize Database Schema")
    print("-" * 70)
    try:
        db = DatabaseManager()
        db.initialize_database()
        print("✅ Database schema initialized!")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False
    
    # Check if we're in the right directory
    if not os.path.exists("srd_importer.py"):
        print("❌ Error: srd_importer.py not found!")
        print("   Please run this script from: /home/kazeyami/bot/")
        return False
    
    if not os.path.exists("srd"):
        print("❌ Error: SRD files not found at ./srd/")
        print("   Make sure the following files exist:")
        print("   - ./srd/spells.json")
        print("   - ./srd/monsters.json")
        return False
    
    print("\n📋 STEP 1: Verify SRD Files")
    print("-" * 70)
    
    srd_files = [
        ("spells.json", "Spell definitions"),
        ("monsters.json", "Monster stat blocks"),
    ]
    
    for filename, desc in srd_files:
        path = f"srd/{filename}"
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✓ {filename:20s} ({size:,} bytes) - {desc}")
        else:
            print(f"  ✗ {filename:20s} - MISSING")
    
    print("\n📚 STEP 2: Run SRD Importer")
    print("-" * 70)
    print("This will import ~700+ records into your database:")
    print("  • ~400 spells from PHB 2024")
    print("  • ~300+ monsters from MM 2024")
    print("  • 27 weapons with mastery properties")
    print()
    
    response = input("Ready to import? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Import cancelled")
        return False
    
    print("\n🚀 Starting import...\n")
    
    try:
        result = subprocess.run(
            [sys.executable, "srd_importer.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print("\n" + "=" * 70)
            print("✅ SRD Import Successful!")
            print("=" * 70)
            print("\n📝 Your database now includes:")
            print("  • srd_spells table - Spell lookup by level/name")
            print("  • srd_monsters table - Monster stat blocks by CR")
            print("  • weapon_mastery table - 2024 weapon properties")
            print("\n📌 Next Steps:")
            print("  1. Update dnd_newest.py to import query functions:")
            print("     from database import get_spell_by_name, search_monsters_by_cr")
            print("  2. Create slash commands using the new SRD data")
            print("  3. Deploy your bot with enhanced D&D capabilities!")
            print("\n💡 Useful Query Examples:")
            print("""
    # In dnd_newest.py:
    from database import (
        get_spell_by_name,
        search_spells_by_level,
        get_monster_by_name,
        search_monsters_by_cr,
        get_weapon_mastery
    )
    
    # Get a spell
    spell = get_spell_by_name("fireball")
    
    # Get monsters by challenge rating
    monsters = search_monsters_by_cr(2, 4)  # CR 2-4
    
    # Get weapon info
    sword = get_weapon_mastery("longsword")
            """)
            return True
        else:
            print("\n❌ Import failed!")
            return False
    
    except Exception as e:
        print(f"\n❌ Error running importer: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
