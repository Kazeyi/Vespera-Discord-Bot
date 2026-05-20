import os
import re

FUNCS = [
    "get_cached", "set_cache", "clear_cache", "clear_all_cache", 
    "save_user_language", "save_user_style", "get_target_language", 
    "get_user_global_style", "get_mod_settings", "save_mod_settings", 
    "get_vip_role_id", "get_server_model_name", "update_user_reputation", 
    "get_user_reputation", "save_dnd_config", "get_dnd_config", 
    "update_dnd_location", "update_dnd_summary", "update_dnd_rulebook", 
    "update_game_mode", "save_active_party", "update_quest_data", 
    "get_dnd_campaign_data", "advance_campaign_phase", "reset_campaign", 
    "add_dnd_history", "get_dnd_history", "add_lore", "get_lore", 
    "update_character", "get_character", "batch_update_destiny", 
    "update_character_destiny", "get_session_protagonist", "add_combatant", 
    "add_monster_combatant", "update_combatant_hp", "update_combatant_condition", 
    "get_combatant_conditions", "remove_combatant", "get_combat_order", 
    "clear_combat", "perform_long_rest_db", "add_rule", "lookup_rule", 
    "start_session", "end_session", "record_command_usage", "vacuum_database", 
    "backup_database", "get_spell_by_name", "search_spells_by_level", 
    "get_monster_by_name", "search_monsters_by_cr", "get_weapon_mastery", 
    "search_weapons_by_type", "save_session_mode", "get_session_mode", 
    "update_session_tone", "save_legacy_data", "get_legacy_data", 
    "save_soul_remnant", "get_soul_remnants", "mark_remnant_defeated", 
    "save_chronicles", "get_chronicles", "update_total_years", 
    "save_void_cycle_data", "get_void_cycle_data"
]

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    funcs_pattern = "|".join(FUNCS)

    # We need to replace `FUNC(` with `await asyncio.to_thread(FUNC, `
    # But only if it's not already preceded by `asyncio.to_thread(`
    # and only if it's not in a `def FUNC(`
    # We can use regex with negative lookbehinds.
    
    # Regex breakdown:
    # (?<!def\s)          -> Not preceded by "def "
    # (?<!to_thread\()    -> Not preceded by "to_thread("
    # \b({funcs})\s*\(    -> Matches the function name followed by optional spaces and an open parenthesis
    
    pattern = re.compile(rf'(?<!def\s)(?<!to_thread\()(?<!\.)\b({funcs_pattern})\s*\(')
    
    # Replacement string
    # We insert the await asyncio.to_thread( prefix and append the comma and space
    # BUT wait! What if the function takes NO arguments?
    # e.g. `clear_cache()`
    # the regex matches `clear_cache(`
    # replacement: `await asyncio.to_thread(clear_cache, `
    # Result: `await asyncio.to_thread(clear_cache, )`
    # In python, `func(a, )` is valid, and `to_thread(clear_cache, )` is valid!
    
    content, count = pattern.subn(r'await asyncio.to_thread(\1, ', content)
    
    # Now we need to fix the case where there were no arguments: `await asyncio.to_thread(FUNC, )`
    # Just to be extremely clean, we can replace `, )` with `)`
    content = re.sub(r',\s*\)', ')', content)
    
    if count > 0:
        # Add import asyncio if missing
        if 'import asyncio' not in content:
            # Add it right after other imports
            content = "import asyncio\n" + content
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Refactored {count} instances in {filepath}")

def main():
    bot_dir = '/home/kazeyami/bot'
    cogs_dir = os.path.join(bot_dir, 'cogs')
    
    # Also check other files if needed
    files_to_check = []
    for root, _, files in os.walk(cogs_dir):
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
                
    for filepath in files_to_check:
        refactor_file(filepath)

if __name__ == '__main__':
    main()
