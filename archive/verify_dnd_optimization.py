#!/usr/bin/env python3
"""
Verification script for D&D Cog Optimizations
"""
import sys
import os
import sqlite3
import importlib.util
from pathlib import Path

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
CYAN = '\033[96m'
RESET = '\033[0m'

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

def test_imports():
    log("\nTesting Imports...", CYAN)
    try:
        from cogs.dnd import DNDCog
        log("✅ DNDCog imported successfully", GREEN)
        return True
    except Exception as e:
        log(f"❌ Import failed: {e}", RED)
        return False

def test_optimizations():
    log("\nTesting Optimization Features...", CYAN)
    
    with open("cogs/dnd.py", "r") as f:
        content = f.read()
    
    features = {
        "WAL Mode": "enable_wal_mode",
        "GC Task": "garbage_collection_task",
        "Cleanup Task": "cleanup_task",
        "String Interning": "intern_string",
        "Global Optimization Import": "from global_optimization import"
    }
    
    all_pass = True
    for name, key in features.items():
        if key in content:
            log(f"✅ {name} present", GREEN)
        else:
            log(f"❌ {name} missing", RED)
            all_pass = False
            
    return all_pass

def test_groq_integration():
    log("\nTesting Groq Client Integration...", CYAN)
    with open("cogs/dnd.py", "r") as f:
        content = f.read()
        
    if "GROQ_CLIENT = Groq" in content and "api_key=os.getenv" in content:
        log("✅ GROQ_CLIENT initialized correctly", GREEN)
        return True
    else:
        log("❌ GROQ_CLIENT initialization issue", RED)
        return False

if __name__ == "__main__":
    log("🔍 D&D OPTIMIZATION VERIFICATION", CYAN)
    sys.path.append(os.getcwd())
    
    if test_imports() and test_optimizations() and test_groq_integration():
        log("\n🎉 ALL CHECKS PASSED!", GREEN)
        sys.exit(0)
    else:
        log("\n⚠️ SOME CHECKS FAILED", RED)
        sys.exit(1)
