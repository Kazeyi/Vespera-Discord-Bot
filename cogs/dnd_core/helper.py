import sys
import os
import discord
from discord import app_commands
from database import get_dnd_config
from .rules import ActionEconomyValidator

# --- HELPER FUNCTIONS ---
async def validate_dnd_access(i):
    """Optimized validation function"""
    try:
        if i.user.guild_permissions.manage_guild:
            return True
        s = get_dnd_config(i.guild.id)
        if not s:
            return False
        role_id = s[4] if len(s) > 4 else None
        if not role_id or role_id == "None":
            return True
        role = i.guild.get_role(int(role_id))
        return True if not role or role in i.user.roles else False
    except Exception:
        return False

def is_dnd_player():
    async def predicate(interaction):
        return await validate_dnd_access(interaction)
    return app_commands.check(predicate)

def get_hp_emoji(curr, max_hp):
    """Optimized HP emoji function"""
    if max_hp <= 0:
        return "⚪"
    ratio = curr / max_hp
    if ratio > 0.5:
        return "💚"
    elif ratio > 0.1:
        return "🧡"
    return "💔"

def generate_truth_block(action: str, character_data: dict = None, target_data: dict = None, 
                        phase: int = 1, guild_id: int = None, location: str = None) -> str:
    """
    Generate a truth block for pre-computed mechanics to prevent hallucinations.
    
    Args:
        action: Player's action description
        character_data: Character stats (optional)
        target_data: Target stats (optional)
        phase: Campaign phase (for legacy haunting)
        guild_id: Guild ID (for legacy character lookup)
        location: Current location (for zone tags)
    
    Returns:
        Truth block string to prepend to AI prompt
    """
    truth_lines = []
    
    # Add TRUTH BLOCK header
    truth_lines.append("=" * 60)
    truth_lines.append("GAME ENGINE TRUTH BLOCK - USE THESE EXACT VALUES")
    truth_lines.append("=" * 60)
    truth_lines.append("")
    
    # === PHASE-SPECIFIC WORLD STATE ===
    # Critical for preventing anachronistic narration
    if phase == 1:
        truth_lines.append("[WORLD STATE: PHASE 1 - FOUNDER ERA]")
        truth_lines.append("Time Period: Classic Medieval High Fantasy")
        truth_lines.append("Magic Style: Chaotic chants and wild incantations")
        truth_lines.append("Weapons: Traditional medieval swords, axes, bows")
        truth_lines.append("Narration Style: Epic fantasy, kingdoms and legends")
        truth_lines.append("")
    elif phase == 2:
        truth_lines.append("[WORLD STATE: PHASE 2 - LEGEND ERA]")
        truth_lines.append("Time Period: 20-50 years after Phase 1")
        truth_lines.append("Magic Style: Early systematization, ritualized spellcasting")
        truth_lines.append("Weapons: Enchanted blades with early runic circuits")
        truth_lines.append("Tech Level: Hybrid craftwork, magic-powered devices emerging")
        truth_lines.append("Narration Style: Consequences of past decisions visible, convergence beginning")
        truth_lines.append("")
    elif phase == 3:
        truth_lines.append("[WORLD STATE: PHASE 3 - INTEGRATED ERA]")
        truth_lines.append("Time Period: 500-1000+ years later, Modern Sci-Fantasy Civilization")
        truth_lines.append("")
        truth_lines.append("⚠️ CRITICAL TERMINOLOGY - USE THESE EXACT TERMS:")
        truth_lines.append("  • SWORDS = 'High-Frequency Neural Conductors' or 'Aura Conductors'")
        truth_lines.append("  • SPELLS = 'Calculated Execution Sequences' or 'Arcane Algorithms'")
        truth_lines.append("  • MAGIC = 'Systematic Mana Processing' or 'Bio-Energy Circuits'")
        truth_lines.append("  • CASTING = 'Executing a Sequence' or 'Running an Algorithm'")
        truth_lines.append("  • MANA = 'Mana Units' or 'Energy Reserves'")
        truth_lines.append("")
        truth_lines.append("Technology Integration:")
        truth_lines.append("  • Swords are synapse extensions for nervous system")
        truth_lines.append("  • Spells are pre-programmed execution chains")
        truth_lines.append("  • Magic and tech are unified, not separate")
        truth_lines.append("  • Cities are modern but organized as Kingdoms/Sects/Empires")
        truth_lines.append("")
        truth_lines.append("Narration Requirements:")
        truth_lines.append("  • Use sci-fi + fantasy blended terminology")
        truth_lines.append("  • Describe magic as scientific and calculated")
        truth_lines.append("  • Weapons are sophisticated tech, not medieval relics")
        truth_lines.append("  • Maintain 'Sword & Magic' identity but modernized")
        truth_lines.append("")
    
    # Add character specialization if Phase 3
    if phase == 3 and character_data:
        specialization = character_data.get('specialization_path', 'unspecialized')
        if specialization == 'aura':
            truth_lines.append("[CHARACTER SPECIALIZATION: AURA ACCELERATION]")
            truth_lines.append("Path: The Circuit - Internal bio-energy and physical overclocking")
            truth_lines.append("Combat Style: Sword acts as neural conductor, direct nervous system interface")
            truth_lines.append("Abilities: Synapse-based attacks, bio-resonance defense, neural echoes")
            truth_lines.append("Narration: Emphasize physical prowess enhanced by bio-circuits")
            truth_lines.append("")
        elif specialization == 'sorcery':
            truth_lines.append("[CHARACTER SPECIALIZATION: SYSTEMATIC SORCERY]")
            truth_lines.append("Path: The Sequence - External mana manipulation via logical calculation")
            truth_lines.append("Combat Style: Sword acts as processor for executing spell programs")
            truth_lines.append("Abilities: Parallel casting, spell compilation, mana optimization")
            truth_lines.append("Narration: Emphasize precise calculations and algorithmic magic")
            truth_lines.append("")
    
    # === ACTION ECONOMY VALIDATION ===
    # Check if player is trying to do too much in one turn
    action_validation = ActionEconomyValidator.validate_action_economy(action, character_data)
    
    # Add Extra Attack info to truth block if applicable
    if character_data and action_validation.get('actions_used', {}).get('action', 0) > 0:
        char_level = character_data.get('level', 1)
        char_class = character_data.get('class', '').lower()
        if char_class in ['fighter', 'paladin', 'ranger', 'barbarian', 'monk'] and char_level >= 5:
             truth_lines.append(f"[EXTRA ATTACK] {char_name} can attack multiple times per Action.")
             
    if not action_validation['is_valid']:
        truth_lines.append(f"⚠️ RULE VIOLATION DETECTED: {action_validation['warning']}")
        truth_lines.append(f"INSTRUCTION: {action_validation['enforcement_instruction']}")
    else:
        truth_lines.append("✅ ACTION ECONOMY CHECK: VALID")
        
    return "\n".join(truth_lines)
