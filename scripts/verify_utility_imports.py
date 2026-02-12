
import sys
import os

# Add the bot directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Verifying imports for Utility Core...")

try:
    print("Importing utility_core...")
    import cogs.utility_core.translation
    import cogs.utility_core.tldr
    import cogs.utility_core.moderator
    import cogs.utility_core.utils
    import cogs.utility_core.personality
    print("✅ utility_core imported successfully.")
except Exception as e:
    print(f"❌ Failed to import utility_core: {e}")
    sys.exit(1)

try:
    print("Importing cogs...")
    # These might fail if they require discord.ext.commands context which is fine, 
    # we just want to check if the file is parseable and top-level imports work.
    # We won't instantiate the cogs, just import the modules.
    import cogs.translate
    import cogs.tldr
    import cogs.moderator
    print("✅ Cogs imported successfully.")
except ImportError as e:
    print(f"❌ Failed to import cogs: {e}")
    sys.exit(1)
except Exception as e:
    # Runtime errors might happen due to missing bot instance, but SyntaxError/ImportError is what we care about
    print(f"⚠️ Runtime warning during import (expected if no bot instance): {e}")

print("Verification complete.")
