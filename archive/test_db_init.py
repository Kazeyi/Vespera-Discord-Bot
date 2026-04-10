#!/usr/bin/env python3
"""Test script to verify generational tables are created"""
import sqlite3
import sys
import os

# Path to database
DB_FILE = "bot_database.db"

def test_table_creation():
    """Test if all generational tables exist"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Get all table names
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in c.fetchall()}
        
        required_tables = {
            'dnd_session_mode',
            'dnd_legacy_data',
            'dnd_soul_remnants',
            'dnd_chronicles'
        }
        
        print("🔍 Checking for generational system tables...")
        print(f"Existing tables: {existing_tables}\n")
        
        all_exist = True
        for table in required_tables:
            if table in existing_tables:
                print(f"✅ {table}")
                # Get column info
                c.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in c.fetchall()]
                print(f"   Columns: {', '.join(cols)}\n")
            else:
                print(f"❌ {table} - MISSING!\n")
                all_exist = False
        
        conn.close()
        
        if all_exist:
            print("🎉 All generational tables exist!")
            return True
        else:
            print("⚠️ Some tables are missing - will be created on cog load")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_table_creation()
