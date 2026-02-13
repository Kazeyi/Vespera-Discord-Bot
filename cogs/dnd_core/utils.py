import sys
import os
import discord
from discord import app_commands

# Ensure we can import from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import get_dnd_config

async def validate_dnd_access(i: discord.Interaction) -> bool:
    """Optimized validation function"""
    try:
        # Check administrator permissions first
        if hasattr(i.user, "guild_permissions") and i.user.guild_permissions.manage_guild:
            return True
            
        s = get_dnd_config(i.guild.id)
        if not s:
            return False
        
        # Check specific role requirement
        # Config structure dependent: [0] parent, [1] loc, [2] summary, [3] name, [4] role_id
        role_id = s[4] if len(s) > 4 else None
        
        if not role_id or role_id == "None" or str(role_id) == "0":
            return True
            
        role = i.guild.get_role(int(role_id))
        return True if not role or role in i.user.roles else False
    except Exception as e:
        # print(f"Validation error: {e}")
        return False

def is_dnd_player():
    """Decorator to check if user has D&D access"""
    async def predicate(interaction: discord.Interaction) -> bool:
        return await validate_dnd_access(interaction)
    return app_commands.check(predicate)

def get_hp_emoji(curr: int, max_hp: int) -> str:
    """Optimized HP emoji function"""
    if max_hp <= 0:
        return "⚪"
    ratio = curr / max_hp
    if ratio > 0.5:
        return "💚"
    elif ratio > 0.1:
        return "🧡"
    return "💔"
