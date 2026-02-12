#!/usr/bin/env python3
"""
Fix D&D database schema - adds missing columns
Run this if you get "no such column" errors
"""
import sqlite3
import os

DB_FILE = os.path.abspath("bot_database.db")
print(f"🔧 Fixing D&D Database Schema at: {DB_FILE}")

if not os.path.exists(DB_FILE):
    print("❌ Database file not found!")
    exit(1)

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

try:
    # Check if table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dnd_config'")
    if not c.fetchone():
        print("❌ dnd_config table doesn't exist! Run the bot to create it first.")
        conn.close()
        exit(1)
    
    # Get current columns
    c.execute("PRAGMA table_info(dnd_config)")
    existing_columns = [row[1] for row in c.fetchall()]
    print(f"📋 Existing columns: {', '.join(existing_columns)}")
    
    # Add missing columns
    columns_to_add = {
        "campaign_summary": "TEXT",
        "party_stats": "TEXT", 
        "dnd_role_id": "TEXT",
        "rulebook": "TEXT",
        "active_party": "TEXT",
        "campaign_phase": "INTEGER DEFAULT 1",
        "legends": "TEXT"
    }
    
    added = []
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE dnd_config ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️  Failed to add {col_name}: {e}")
        else:
            print(f"✓ Column {col_name} already exists")
    
    if added:
        conn.commit()
        print(f"\n✅ Successfully added {len(added)} column(s): {', '.join(added)}")
    else:
        print("\n✅ All columns already exist - schema is up to date!")
    
    # Verify final schema
    c.execute("PRAGMA table_info(dnd_config)")
    final_columns = [row[1] for row in c.fetchall()]
    print(f"\n📋 Final columns: {', '.join(final_columns)}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()

print("\n✅ Database schema fix complete!")
