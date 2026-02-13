import sys
import os
import re
import random
import discord
from datetime import datetime
from typing import List, Dict, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import get_combat_order, update_combatant_hp, remove_combatant
from .ai import generate_text
from .constants import FAST_MODEL

class CombatTracker:
    """Optimized combat tracker with reference numbers"""
    
    @staticmethod
    def get_combat_with_refs(thread_id: int) -> List[Dict]:
        """Get combatants with reference numbers"""
        combatants = get_combat_order(thread_id)
        result = []
        
        for idx, (uid, name, init, curr_hp, max_hp, is_monster, conditions) in enumerate(combatants, 1):
            result.append({
                "ref": idx,
                "id": uid,
                "name": name,
                "init": init,
                "hp": curr_hp,
                "max_hp": max_hp,
                "is_monster": is_monster,
                "conditions": conditions,
                "display": f"[{idx}] {name} ({curr_hp}/{max_hp})"
            })
        
        return result
    
    @staticmethod
    def apply_damage_by_ref(thread_id: int, ref: int, damage: int) -> Optional[Dict]:
        """Apply damage using reference number"""
        combatants = CombatTracker.get_combat_with_refs(thread_id)
        
        for combatant in combatants:
            if combatant["ref"] == ref:
                new_hp = update_combatant_hp(thread_id, combatant["id"], -damage)
                
                if new_hp <= 0 and combatant["is_monster"] == 1:
                    remove_combatant(thread_id, combatant["id"])
                    combatant["status"] = "defeated"
                else:
                    combatant["hp"] = new_hp
                    combatant["status"] = "damaged"
                
                return combatant
        
        return None
    
    @staticmethod
    def get_combat_summary(thread_id: int) -> str:
        """Get compact combat summary"""
        combatants = CombatTracker.get_combat_with_refs(thread_id)
        
        if not combatants:
            return "No active combat."
        
        players = [c for c in combatants if c["is_monster"] == 0]
        monsters = [c for c in combatants if c["is_monster"] == 1]
        npcs = [c for c in combatants if c["is_monster"] == 2]
        
        lines = []
        
        if players:
            lines.append("**Players:**")
            for c in players:
                hp_emoji = "💚" if c["hp"] > c["max_hp"] * 0.5 else "🧡" if c["hp"] > c["max_hp"] * 0.1 else "💔"
                lines.append(f"  {hp_emoji} {c['name']}: {c['hp']}/{c['max_hp']}")
        
        if monsters:
            lines.append("**Enemies:**")
            for c in monsters[:5]:
                lines.append(f"  [{c['ref']}] {c['name']}: {c['hp']}/{c['max_hp']}")
            if len(monsters) > 5:
                lines.append(f"  ...and {len(monsters) - 5} more")
        
        if npcs:
            lines.append("**Allies:**")
            for c in npcs[:3]:
                lines.append(f"  {c['name']}: {c['hp']}/{c['max_hp']}")
        
        return "\n".join(lines)

class KillCamNarrator:
    """
    Generate cinematic "Final Blow" narration when an enemy is defeated.
    """
    
    @staticmethod
    async def generate_kill_cam(
        character_name: str,
        monster_name: str,
        player_action: str,
        final_damage: int,
        attack_type: str = "unknown"
    ) -> str:
        prompt = f"""Describe a CINEMATIC and BRUTAL finishing move in 1-2 sentences. Make it dramatic and memorable.

Context:
- Victor: {character_name}
- Defeated: {monster_name}
- Finishing move: {player_action}
- Damage: {final_damage} HP
- Attack type: {attack_type}

Make it dramatic, visceral, and epic. Use action movie language.
Example: 'The blade pierces through its heart with a sickening crunch. The creature's scream echoes as it collapses.'

Your narration (2 sentences max):"""
        
        narration = await generate_text(prompt, FAST_MODEL, temperature=0.8, max_tokens=150)
        
        if narration:
            return narration
        
        # Fallback
        fallback_narrations = [
            f"{character_name} strikes the final, decisive blow. {monster_name} falls, defeated at last.",
            f"With one last surge of power, {character_name} brings {monster_name} to its knees. Victory is theirs.",
            f"The battle is over. {monster_name} lies defeated by {character_name}'s skill and determination.",
        ]
        return random.choice(fallback_narrations)
    
    @staticmethod
    def create_kill_cam_embed(character_name: str, monster_name: str, narration: str) -> discord.Embed:
        embed = discord.Embed(
            title="☠️ FINAL BLOW ☠️",
            description=narration,
            color=0x000000,
            timestamp=datetime.now()
        )
        embed.add_field(name="Victor", value=character_name, inline=True)
        embed.add_field(name="Defeated", value=monster_name, inline=True)
        embed.set_footer(text="Vespera Chronicles • Legendary moment recorded")
        return embed

class ReactionSuggestionEngine:
    THREAT_KEYWORDS = {
        "fireball": {"threat": "AoE Spell", "reactions": ["Cast Counterspell", "Evasive Maneuver", "Take Cover"]},
        "lightning bolt": {"threat": "AoE Spell", "reactions": ["Cast Counterspell", "Dodge Roll", "Shield Ally"]},
        "magic missile": {"threat": "Direct Spell", "reactions": ["Cast Counterspell", "Shield Spell"]},
        "counterspell": {"threat": "Counter-magic", "reactions": ["Quicken Spell", "Cast Silently"]},
        "dispel magic": {"threat": "Magic Suppression", "reactions": ["Renew Concentration", "Prepare Backup Spell"]},
        
        "attack": {"threat": "Melee Attack", "reactions": ["Parry", "Dodge", "Riposte"]},
        "charge": {"threat": "Charging Attack", "reactions": ["Ready Action", "Hold Ground", "Counter-charge"]},
        "grapple": {"threat": "Grapple Attempt", "reactions": ["Escape Artist", "Break Free", "Reverse Grapple"]},
        
        "falling": {"threat": "Environmental Damage", "reactions": ["Cast Featherfall", "Grab Ledge", "Use Rope"]},
        "fire": {"threat": "Fire Damage", "reactions": ["Take Cover", "Extinguish", "Resistance Spell"]},
        "poison": {"threat": "Poison", "reactions": ["Antitoxin", "Lesser Restoration", "Hold Breath"]},
    }
    
    @staticmethod
    def analyze_threat(action: str, character_data: dict = None, combat_context: str = "") -> dict:
        action_lower = action.lower()
        threat_level = "LOW"
        threat_type = "Unknown"
        suggested_reactions = ["Observe Carefully", "Ready Action"]
        
        for threat_key, threat_info in ReactionSuggestionEngine.THREAT_KEYWORDS.items():
            if threat_key in action_lower:
                threat_type = threat_info["threat"]
                suggested_reactions = threat_info["reactions"].copy()
                
                if "aoe" in threat_info["threat"].lower():
                    threat_level = "HIGH"
                elif "spell" in threat_info["threat"].lower():
                    threat_level = "MEDIUM"
                elif "melee" in threat_info["threat"].lower():
                    threat_level = "MEDIUM"
                else:
                    threat_level = "LOW"
                break
        
        if character_data:
            spellcasting_ability = character_data.get('spellcasting_ability')
            if spellcasting_ability:
                if "Counterspell" not in suggested_reactions and threat_level in ["MEDIUM", "HIGH"]:
                    suggested_reactions.insert(0, "Cast Counterspell")
            
            class_type = character_data.get('class', '').lower()
            if "rogue" in class_type:
                suggested_reactions.append("Cunning Action")
            elif "ranger" in class_type:
                suggested_reactions.append("Hunter's Reaction")
            elif "warlock" in class_type:
                suggested_reactions.append("Eldritch Reaction")
        
        return {
            "threat_type": threat_type,
            "threat_level": threat_level,
            "suggested_reactions": list(dict.fromkeys(suggested_reactions))[:4],
            "context": f"Incoming {threat_type}: {action[:50]}..."
        }

# --- KILL CAM NARRATOR ---
class KillCamNarrator:
    """
    Generate cinematic "Final Blow" narration when an enemy is defeated.
    Creates dramatic finishing move descriptions based on player actions.
    """
    
    @staticmethod
    async def generate_kill_cam(
        character_name: str,
        monster_name: str,
        player_action: str,
        final_damage: int,
        attack_type: str = "unknown"
    ) -> str:
        """
        Generate a cinematic narration for the final blow.
        """
        prompt = f"""Describe a CINEMATIC and BRUTAL finishing move in 1-2 sentences. Make it dramatic and memorable.

Context:
- Victor: {character_name}
- Defeated: {monster_name}
- Finishing move: {player_action}
- Damage: {final_damage} HP
- Attack type: {attack_type}

Make it dramatic, visceral, and epic. Use action movie language.
Example: 'The blade pierces through its heart with a sickening crunch. The creature's scream echoes as it collapses.'

Your narration (2 sentences max):"""
        
        summary = await generate_text(prompt, FAST_MODEL, max_tokens=150, temperature=0.8)
            
        if summary:
            return summary
        else:
            # Fallback narration if API times out
            fallback_narrations = [
                f"{character_name} strikes the final, decisive blow. {monster_name} falls, defeated at last.",
                f"With one last surge of power, {character_name} brings {monster_name} to its knees. Victory is theirs.",
                f"The battle is over. {monster_name} lies defeated by {character_name}'s skill and determination.",
            ]
            return random.choice(fallback_narrations)
    
    @staticmethod
    def create_kill_cam_embed(character_name: str, monster_name: str, narration: str) -> discord.Embed:
        """Create a visual embed for the kill cam moment"""
        embed = discord.Embed(
            title="☠️ FINAL BLOW ☠️",
            description=narration,
            color=0x000000,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Victor", value=character_name, inline=True)
        embed.add_field(name="Defeated", value=monster_name, inline=True)
        embed.set_footer(text="Vespera Chronicles • Legendary moment recorded")
        
        return embed

# --- PRE-COMPUTATION ENGINE ---
class PrecomputationEngine:
    """Pre-compute dice rolls and outcomes to prevent AI hallucination"""
    
    @staticmethod
    def roll_dice(dice_string: str) -> tuple:
        """Parse dice strings like '2d6+3' and return (total, individual_rolls, modifier)"""
        if not dice_string or not isinstance(dice_string, str):
            return (0, [], 0)
        
        # Remove whitespace
        dice_string = dice_string.lower().replace(" ", "")
        
        try:
            # Check for dice pattern (e.g., 2d6+3)
            dice_match = re.match(r"^(\d+)d(\d+)([+\-]\d+)?$", dice_string)
            if dice_match:
                num_dice = int(dice_match.group(1))
                dice_type = int(dice_match.group(2))
                modifier = int(dice_match.group(3) or 0)
                
                # Roll individual dice
                rolls = [random.randint(1, dice_type) for _ in range(num_dice)]
                total = sum(rolls) + modifier
                
                return (total, rolls, modifier)
            
            # Check for single die (e.g., d20+5)
            single_match = re.match(r"^d(\d+)([+\-]\d+)?$", dice_string)
            if single_match:
                dice_type = int(single_match.group(1))
                modifier = int(single_match.group(2) or 0)
                roll = random.randint(1, dice_type)
                return (roll + modifier, [roll], modifier)
                
        except Exception:
            pass
        
        return (0, [], 0)
    
    @staticmethod
    def compute_attack_result(attack_bonus: int, target_ac: int, conditions: str = "") -> dict:
        """Pre-compute attack roll results with automatic condition handling (D&D 2024)"""
        # Check for advantage/disadvantage from conditions
        conditions_lower = conditions.lower() if conditions else ""
        
        # Advantage conditions (D&D 2024)
        has_advantage = any(cond in conditions_lower for cond in [
            "prone" and "melee",  # Attacking prone target in melee
            "restrained",         # Attacking restrained target
            "paralyzed",          # Attacking paralyzed target
            "stunned",            # Attacking stunned target
            "unconscious",        # Attacking unconscious target
            "invisible" and "attacker"  # Being invisible while attacking
        ])
        
        # Disadvantage conditions (D&D 2024)
        has_disadvantage = any(cond in conditions_lower for cond in [
            "prone" and "ranged",  # Attacking prone target from range
            "blinded",             # Attacker is blinded
            "frightened",          # Attacker is frightened of target
            "poisoned",            # Attacker is poisoned
            "restrained" and "attacker",  # Attacker is restrained
            "invisible" and "target"      # Target is invisible
        ])
        
        # Roll with advantage/disadvantage
        if has_advantage and not has_disadvantage:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            final_roll = max(roll1, roll2)
            roll_info = f"Advantage ({roll1}, {roll2})"
            is_crit = (roll1 == 20 or roll2 == 20)
        elif has_disadvantage and not has_advantage:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            final_roll = min(roll1, roll2)
            roll_info = f"Disadvantage ({roll1}, {roll2})"
            is_crit = (final_roll == 20)
        else:
            final_roll = random.randint(1, 20)
            roll_info = f"Straight Roll ({final_roll})"
            is_crit = (final_roll == 20)
        
        total_to_hit = final_roll + attack_bonus
        is_hit = total_to_hit >= target_ac
        
        return {
            "roll": final_roll,
            "total": total_to_hit,
            "is_hit": is_hit,
            "is_crit": is_crit,
            "info": roll_info,
            "advantage": has_advantage,
            "disadvantage": has_disadvantage
        }
