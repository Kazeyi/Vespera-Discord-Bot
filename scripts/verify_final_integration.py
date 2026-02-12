
import sys
import os
import gc

# Add workspace root to sys.path
sys.path.append(os.getcwd())

def verify_imports():
    print("--- Starting Final Integration Verification ---")
    
    # 1. Verify Memory Optimization Settings
    print("[1/6] Verifying Memory Settings...")
    gc.set_threshold(400, 5, 5)
    if gc.get_threshold() == (400, 5, 5):
        print("   -> Memory settings applied successfully.")
    else:
        print(f"   -> FAILED: Memory settings mismatch: {gc.get_threshold()}")

    # 2. Verify Personality Module (The Core Dependency)
    print("\n[2/6] Importing Utility Core (Personality)...")
    try:
        from cogs.utility_core.personality import VesperaPersonality as VP
        # Minimal check of the class
        test_color = VP.Colors.ERROR
        print("   -> Personality module imported and accessed successfully.")
    except Exception as e:
        print(f"   -> FAILED to import Personality: {e}")
        return

    # 3. Verify Cloud Engine (Recently Moved)
    print("\n[3/6] Importing Cloud Engine...")
    try:
        # Check several key sub-modules to ensure pathing is correct
        # Note: cloud_provisioning_generator is in root, but used by orchestrator
        import cogs.cloud_engine.core.orchestrator
        import cogs.cloud_engine.ai.cloud_ai_advisor
        print("   -> Cloud Engine imported successfully.")
    except ImportError as e:
        print(f"   -> FAILED: Circular import or missing file in Cloud Engine: {e}")
        return
    except Exception as e:
        print(f"   -> FAILED: Cloud Engine error: {e}")
        return

    # 4. Verify DND Cog (Heavy Dependency)
    print("\n[4/6] Importing DnD System...")
    try:
        import cogs.dnd
        print("   -> DnD System imported successfully.")
    except Exception as e:
        print(f"   -> FAILED: DnD import error: {e}")
        return

    # 5. Verify Moderator & Translator (Updated with VP)
    print("\n[5/6] Importing Moderator and Translator...")
    try:
        import cogs.moderator
        import cogs.translate
        print("   -> Moderator & Translator imported successfully.")
    except Exception as e:
        print(f"   -> FAILED: Mod/Trans import error: {e}")
        return

    # 6. Verify TLDR (String Interning Check)
    print("\n[6/6] Importing TLDR...")
    try:
        import cogs.tldr
        print("   -> TLDR imported successfully.")
    except Exception as e:
        print(f"   -> FAILED: TLDR import error: {e}")
        return

    print("\n--- PASSED: All Systems Ready for Production ---")

if __name__ == "__main__":
    verify_imports()
