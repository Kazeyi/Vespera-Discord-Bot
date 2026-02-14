# 🧹 COMMAND CLEANUP & GLOBAL SYNC GUIDE

## What Was Fixed

### 1. Global Command Sync (Automatic)
✅ **Implemented**: Bot now automatically syncs commands globally on every restart
- **Before**: Had to manually use `!sync` command after each bot restart
- **After**: Commands are registered globally immediately when bot loads
- **Benefit**: No more waiting for command availability

### 2. Database Migration Fix
✅ **Fixed**: Missing database columns (session_mode, current_tone, total_years_elapsed)
- **Before**: Errors accessing non-existent dnd_config columns
- **After**: Automatic migration creates missing columns on bot start
- **How**: DatabaseManager._run_migrations() detects and adds missing columns

### 3. Character Selection Redesigned
✅ **Implemented**: Character selection moved to AFTER launch
- **Before**: Character selection in lobby (visible to all)
- **After**: Character selection modal shown only to players who joined
- **Experience**: Better game flow - like entering a game lobby before loading the map

## Files Modified

### [main.py](../main.py) - Global Sync
- **Changed**: Line 48-51 - Removed TEST_GUILD_ID conditional
- **Now**: Always syncs commands globally
- **Result**: Commands available immediately in all servers

### [cogs/dnd.py](../cogs/dnd.py) - Character Selection & Error Handling
- **Added**: CharacterSelectionModal class - post-launch character picking
- **Added**: CharacterSelectionView class - buttons for character selection
- **Changed**: SessionLobbyView - removed dropdowns, simplified to buttons only
- **Changed**: Removed ModeSelect and CharacterSelect from lobby
- **Added**: Error handling for table operations during migration

### [database.py](../database.py) - Migrations
- **Updated**: _run_migrations() now includes new generational columns
- **Added**: session_mode, current_tone, total_years_elapsed to dnd_config migration
- **Benefit**: Gracefully adds missing columns without data loss

## How Character Selection Now Works

### Session Flow (OLD)
```
/start_session
  ↓
[SessionLobbyView with dropdowns]
  ├─ Mode Dropdown
  ├─ Character Dropdown (per player)
  └─ Launch Button
  ↓
Game starts
```

### Session Flow (NEW) - Better UX
```
/start_session
  ↓
[SessionLobbyView - simple buttons only]
  ├─ Join/Leave buttons
  ├─ Launch Session button
  └─ (Character selection happens AFTER launch!)
  ↓
[CharacterSelectionView appears]
  ├─ "Select Character" button (only for joined players)
  ├─ "Ready" button (confirms selection)
  └─ (Waits for all players to select)
  ↓
Game starts with characters locked in
```

### Benefits
✅ **Cleaner Lobby**: No dropdowns clutter
✅ **Player-Specific**: Only joined players see character selection
✅ **Game-Like**: Similar to actual game launcher (lobby → character select → play)
✅ **Accountability**: Players must join first to select character

## Global Command Sync Details

### Before (Guild-Scoped)
- Commands appeared in one test guild
- Needed `!sync` manually after each restart
- Changes took time to propagate
- Commands missing if bot restarted

### After (Global)
```python
# Always syncs globally on startup
synced = await self.tree.sync()
print(f"🌍 Global Sync: {len(synced)} commands registered globally")
```

- Commands available immediately
- No `!sync` needed after restart
- Consistent across all servers
- Faster deployment

## Database Migration Process

### When It Happens
1. Bot starts → DNDCog loads → _run_migrations() called
2. Checks each table for missing columns
3. Automatically adds: session_mode, current_tone, total_years_elapsed to dnd_config
4. Sets proper defaults:
   - session_mode: "Architect"
   - current_tone: "Standard"
   - total_years_elapsed: 0

### What It Creates
```sql
ALTER TABLE dnd_config ADD COLUMN session_mode TEXT DEFAULT 'Architect';
ALTER TABLE dnd_config ADD COLUMN current_tone TEXT DEFAULT 'Standard';
ALTER TABLE dnd_config ADD COLUMN total_years_elapsed INTEGER DEFAULT 0;
```

### Error Handling
- `try/except` around table operations
- Gracefully skips if migration already ran
- Won't break existing data
- Reports migration status in logs

## Cleaning Up Duplicate Commands

### Option 1: Automatic Cleanup (Fast)
```bash
python3 scripts/clean_app_commands.py -y
# -y flag: Auto-confirm all deletions (no prompts)
```

### Option 2: Interactive Cleanup (Safe)
```bash
python3 scripts/clean_app_commands.py
# Will show what would be deleted, ask for confirmation
```

### Option 3: Purge Specific Commands
```bash
# Delete all versions of a specific command (global + guild)
python3 scripts/clean_app_commands.py -p start_session -p do_action

# -p flag: Can be used multiple times for different commands
```

### What It Does
- Finds duplicate command names
- Keeps guild-scoped versions (preferred)
- Deletes global duplicates
- Handles rate limiting automatically
- Safe retry logic with exponential backoff

### Example Output
```
Logged in. App ID: 123456789. Guilds: 5
Duplicate command name found: 'start_session' → 3 entries
  Deleting global start_session (ID: xxx)
  Keeping guild-scoped start_session in guild 123

Total deleted: 1 duplicate command(s)
```

## Commands Using Generational System

### Affected Commands (now with migration handling)
- `/mode_select` - Choose Architect/Scribe mode
- `/time_skip` - Generate time skips (20-30 or 500-1000 years)
- `/chronicles` - View campaign records
- `/start_session` - Launch session with character selection

### Commands That Work Immediately
- `/import_character` - Import character sheet
- `/do` - Perform action in session
- All other D&D commands

### Note
- Tone shifting happens automatically (stored during session)
- Legacy data saved on time skips
- Soul remnants created from defeated characters
- Chronicles built as phases complete

## Migration Status Check

### How to Verify Migration Ran
```bash
# Look for in bot logs:
"🛠️  Initializing Database Schema..."
"  🔄 Checking for migrations..."
"    ✓ Added column session_mode to dnd_config"
"    ✓ Added column current_tone to dnd_config"
"    ✓ Added column total_years_elapsed to dnd_config"
"💾 Database initialized successfully!"
```

### If Migration Didn't Run
- Restart bot
- Check for error messages in logs
- Verify database file exists and is writable
- Check permissions: `ls -la bot_database.db`

### Troubleshooting
| Problem | Solution |
|---------|----------|
| "Migration failed" | Restart bot - will retry |
| "Permission denied" | Check database ownership: `sudo chown user:group bot_database.db` |
| "No such table" | Database corrupted - restore backup |
| Commands not syncing | Wait 1-2 minutes for global sync, then refresh Discord |

## Quick Reference

| Task | Command |
|------|---------|
| Deploy new code | Restart bot (migration runs automatically) |
| Clean duplicates | `python3 scripts/clean_app_commands.py -y` |
| Check migration | Look for success message in logs |
| View all commands | `/help` command (or Discord app menu) |
| Select session mode | `/mode_select` (buttons will appear) |
| Import character | `/import_character` (then /start_session) |
| Launch session | `/start_session` → Join → Launch (then character select) |

## Important Notes

✅ **Backward Compatible**: Existing campaigns unaffected
✅ **Automatic Migration**: No manual database changes needed
✅ **Error Safe**: Try/except prevents crashes during transition
✅ **Global Sync**: No more manual sync needed
✅ **Character Selection**: Moved to better UX location

## Next Steps

1. ✅ Restart bot (runs migration automatically)
2. ✅ Watch for migration messages in logs
3. ✅ Test commands work globally
4. ✅ Clean duplicates: `python3 scripts/clean_app_commands.py -y`
5. ✅ Test /start_session flow with character selection after launch

---

**Version**: 2.0 - Global Sync & Migration Fixes  
**Status**: ✅ Ready for deployment  
**Date**: January 2026
