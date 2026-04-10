#!/usr/bin/env python3
"""
DEPLOYMENT VERIFICATION GUIDE
Generational Void Cycle System - Full Integration Complete

This script verifies that all system components are ready for deployment.
Run after bot loads to confirm database tables were created successfully.
"""

import sqlite3
import sys

DB_FILE = "bot_database.db"

def verify_post_deployment():
    """Run this AFTER the bot starts to verify tables were created"""
    print("=" * 70)
    print("✅ POST-DEPLOYMENT VERIFICATION (Run after bot loads)")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Check tables exist
        required_tables = ['dnd_session_mode', 'dnd_legacy_data', 'dnd_soul_remnants', 'dnd_chronicles']
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in c.fetchall()}
        
        print("\n📊 DATABASE TABLES:")
        all_present = True
        for table in required_tables:
            if table in existing:
                # Get column count
                c.execute(f"PRAGMA table_info({table})")
                cols = len(c.fetchall())
                print(f"  ✅ {table} ({cols} columns)")
            else:
                print(f"  ❌ {table} - MISSING!")
                all_present = False
        
        conn.close()
        
        if all_present:
            print("\n🎉 DEPLOYMENT SUCCESSFUL!")
            print("All generational system tables created successfully.")
            return True
        else:
            print("\n⚠️ DEPLOYMENT INCOMPLETE!")
            print("Some tables are missing. Check bot logs for errors during cog load.")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    # Run verification
    success = verify_post_deployment()
    
    if success:
        print("\n" + "=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print("1. Test /start_session command - should show mode dropdown + character selects")
        print("2. Test /mode_select command - should set Architect/Scribe mode")
        print("3. Test /time_skip command - should generate 20-30 or 500-1000 year skips")
        print("4. Test lobby - Join, Leave, Continue, Reset Mode, Launch buttons")
        print("5. Verify character selection dropdown shows only user's imported characters")
        print("6. Verify NPC destiny rolls are capped intelligently")
        print("=" * 70)
        sys.exit(0)
    else:
        sys.exit(1)
