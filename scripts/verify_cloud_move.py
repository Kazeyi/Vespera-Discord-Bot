
import sys
import os

sys.path.append(os.getcwd())

print("Verifying Cloud imports...")

try:
    print("Attempting to import cogs.cloud_engine...")
    import cogs.cloud_engine
    print("✅ cogs.cloud_engine imported.")
except Exception as e:
    print(f"❌ Failed to import cogs.cloud_engine: {e}")
    sys.exit(1)

try:
    print("Attempting to import cogs.cloud_engine.ai...")
    import cogs.cloud_engine.ai
    print("✅ cogs.cloud_engine.ai imported.")
except Exception as e:
    print(f"❌ Failed to import cogs.cloud_engine.ai: {e}")
    sys.exit(1)

try:
    print("Attempting to import cogs.cloud (Monolithic Cog)...")
    # cogs.cloud might fail if it requires discord bot instance or partials
    # so we just catch ImportError. 
    # But loading it as module triggers globally scoped code.
    import cogs.cloud
    print("✅ cogs.cloud imported.")
except ImportError as e:
    print(f"❌ Failed to import cogs.cloud: {e}")
    sys.exit(1)
except Exception as e:
    print(f"⚠️ Runtime warning importing cogs.cloud (expected without bot): {e}")

print("Verification complete.")
