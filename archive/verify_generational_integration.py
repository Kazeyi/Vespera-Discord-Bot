#!/usr/bin/env python3
"""
Verification script for Generational Void Cycle System integration
Tests database schema, imports, and code structure
"""

import sqlite3
import sys
import ast

def check_python_syntax(filepath):
    """Check if file has valid Python syntax"""
    try:
        with open(filepath, 'r') as f:
            ast.parse(f.read())
        return True, "✅ Syntax OK"
    except SyntaxError as e:
        return False, f"❌ Syntax Error: {e}"

def check_database_schema():
    """Verify new tables exist in schema definition"""
    try:
        with open('database.py', 'r') as f:
            content = f.read()
        
        required_tables = [
            'dnd_session_mode',
            'dnd_legacy_data',
            'dnd_soul_remnants',
            'dnd_chronicles'
        ]
        
        results = []
        for table in required_tables:
            if f'"{table}"' in content:
                results.append((True, f"✅ {table} table definition found"))
            else:
                results.append((False, f"❌ {table} table definition missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Error reading database.py: {e}")]

def check_dnd_classes():
    """Verify new system classes exist in dnd.py"""
    try:
        with open('cogs/dnd.py', 'r') as f:
            tree = ast.parse(f.read())
        
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        
        required_classes = [
            'SessionModeManager',
            'AutomaticToneShifter',
            'TimeSkipManager',
            'CharacterLockingSystem',
            'LevelProgression'
        ]
        
        results = []
        for cls in required_classes:
            if cls in classes:
                results.append((True, f"✅ {cls} class found"))
            else:
                results.append((False, f"❌ {cls} class missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Error parsing dnd.py: {e}")]

def check_database_functions():
    """Verify new database functions are defined"""
    try:
        with open('database.py', 'r') as f:
            content = f.read()
        
        required_functions = [
            'save_session_mode',
            'get_session_mode',
            'update_session_tone',
            'save_legacy_data',
            'get_legacy_data',
            'save_soul_remnant',
            'get_soul_remnants',
            'mark_remnant_defeated',
            'save_chronicles',
            'get_chronicles',
            'update_total_years'
        ]
        
        results = []
        for func in required_functions:
            if f'def {func}' in content:
                results.append((True, f"✅ {func}() defined"))
            else:
                results.append((False, f"❌ {func}() missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Error checking functions: {e}")]

def check_imports():
    """Verify imports are updated in dnd.py"""
    try:
        with open('cogs/dnd.py', 'r') as f:
            content = f.read()
        
        required_imports = [
            'save_session_mode',
            'get_session_mode',
            'save_legacy_data',
            'save_soul_remnant',
            'get_soul_remnants',
            'save_chronicles',
            'get_chronicles',
            'update_total_years'
        ]
        
        # Check in imports section
        import_section = content[:content.find('load_dotenv()')]
        
        results = []
        for imp in required_imports:
            if imp in import_section:
                results.append((True, f"✅ {imp} imported"))
            else:
                results.append((False, f"❌ {imp} not imported"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Error checking imports: {e}")]

def check_new_commands():
    """Verify new commands are defined"""
    try:
        with open('cogs/dnd.py', 'r') as f:
            content = f.read()
        
        required_commands = [
            'mode_select',
            'chronicles'
        ]
        
        results = []
        for cmd in required_commands:
            if f'async def {cmd}' in content:
                results.append((True, f"✅ /{cmd} command found"))
            else:
                results.append((False, f"❌ /{cmd} command missing"))
        
        return results
    except Exception as e:
        return [(False, f"❌ Error checking commands: {e}")]

def main():
    print("=" * 60)
    print("🔍 Generational Void Cycle System - Verification")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Syntax checks
    print("\n📝 Syntax Validation:")
    db_ok, db_msg = check_python_syntax('database.py')
    print(f"  database.py: {db_msg}")
    all_passed = all_passed and db_ok
    
    dnd_ok, dnd_msg = check_python_syntax('cogs/dnd.py')
    print(f"  cogs/dnd.py: {dnd_msg}")
    all_passed = all_passed and dnd_ok
    
    # 2. Database schema
    print("\n📊 Database Schema Verification:")
    schema_results = check_database_schema()
    for ok, msg in schema_results:
        print(f"  {msg}")
        all_passed = all_passed and ok
    
    # 3. System classes
    print("\n🏗️ System Classes Verification:")
    class_results = check_dnd_classes()
    for ok, msg in class_results:
        print(f"  {msg}")
        all_passed = all_passed and ok
    
    # 4. Database functions
    print("\n🔧 Database Functions Verification:")
    func_results = check_database_functions()
    for ok, msg in func_results:
        print(f"  {msg}")
        all_passed = all_passed and ok
    
    # 5. Imports
    print("\n📦 Import Verification:")
    import_results = check_imports()
    for ok, msg in import_results:
        print(f"  {msg}")
        all_passed = all_passed and ok
    
    # 6. New commands
    print("\n⚙️ New Commands Verification:")
    cmd_results = check_new_commands()
    for ok, msg in cmd_results:
        print(f"  {msg}")
        all_passed = all_passed and ok
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL VERIFICATIONS PASSED")
        print("=" * 60)
        print("\n🚀 Ready for deployment!")
        print("\nNext steps:")
        print("1. Review GENERATIONAL_VOID_CYCLE_INTEGRATION.md")
        print("2. Review GENERATIONAL_VOID_CYCLE_QUICKSTART.md")
        print("3. Deploy updated database.py and cogs/dnd.py")
        print("4. Restart bot to initialize new database tables")
        print("5. Test with /mode_select command")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("=" * 60)
        print("\nPlease review the errors above and fix them.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
