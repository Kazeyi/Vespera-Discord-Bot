"""
==============================================================================
TL;DR COG - JSON-OPTIMIZED VERSION  
==============================================================================
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import re
import os
import sys
import time
import gc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_target_language, get_vip_role_id

from .utility_core.tldr import (
    intern_string,
    smart_truncate_history,
    generate_summary
)
from .utility_core.personality import VesperaPersonality as VP

class TLDRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_cooldowns = {}
        self.processed_cache = {}
        
        self.clear_cache_task.start()
        self.garbage_collection_task.start()
        
        self.ctx_menu = app_commands.ContextMenu(name="TL;DR", callback=self.tldr_message_context)
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.clear_cache_task.cancel()
        self.garbage_collection_task.cancel()
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @tasks.loop(hours=1)
    async def clear_cache_task(self):
        self.processed_cache.clear()
        self.user_cooldowns.clear()
        print("🧹 TL;DR cache cleared")

    @tasks.loop(minutes=30)
    async def garbage_collection_task(self):
        collected = gc.collect()
        if collected > 0:
            print(f"🗑️ TL;DR GC: {collected} objects freed")

    def is_rate_limited(self, user_id):
        now = time.time()
        if now - self.user_cooldowns.get(user_id, 0) < 10:
            return True
        self.user_cooldowns[user_id] = now
        return False

    def clean_content(self, msg):
        return re.sub(r'<a?:\w+:\d+>|http\S+', '', msg.content).strip()

    def format_history(self, messages, vip_role_id):
        lines = []
        for m in messages:
            content = self.clean_content(m)
            if not content:
                continue
            
            name = intern_string(m.author.display_name)
            is_vip = False
            if vip_role_id and isinstance(m.author, discord.Member):
                try:
                    role = m.guild.get_role(int(vip_role_id))
                    if role and role in m.author.roles:
                        is_vip = True
                except:
                    pass
            if m.guild and m.author.id == m.guild.owner_id:
                is_vip = True
            
            tag = "🌟 " if is_vip else ""
            lines.append(f"{tag}{name}: {content}")
        return "\n".join(lines)

    async def tldr_message_context(self, interaction: discord.Interaction, message: discord.Message):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message("⏳ Slow down! (10s cooldown)", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        channel = message.channel
        history = [msg async for msg in channel.history(limit=50, after=message, oldest_first=True)]
        history.insert(0, message)
        
        vip_role = get_vip_role_id(interaction.guild.id)
        
        formatted_text = self.format_history(history, vip_role)
        truncated_text = smart_truncate_history(formatted_text)
        
        lang = get_target_language(interaction.user.id, "English")
        
        data, used_model = await generate_summary(truncated_text, lang, interaction.guild.id)
        
        if not data:
            return await interaction.followup.send("❌ Failed to generate summary.")
            
        topic = data.get("topic", "General Discussion")
        summary = data.get("summary", "No summary generated.")
        sentiment = data.get("sentiment", "neutral").lower()
        actions = data.get("actions", [])
        participants = data.get("key_participants", [])
        
        color = 0x95A5A6 
        if "happy" in sentiment: color = 0x2ECC71 
        elif "tense" in sentiment: color = 0xE74C3C 
        elif "sad" in sentiment: color = 0x3498DB
        elif "neutral" in sentiment: color = 0x95A5A6

        embed = discord.Embed(title=f"📝 TL;DR: {topic}", description=summary, color=color)
        
        if actions:
            action_list = "\n".join([f"• {a}" for a in actions[:5]])
            embed.add_field(name="Action Items", value=action_list, inline=False)
            
        if participants:
            parts = ", ".join(participants[:8])
            embed.add_field(name="Key Participants", value=parts, inline=False)
            
        embed.set_footer(text=f"Model: {used_model} | {len(history)} messages processed")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tldr", description="Summarize the last N messages")
    async def tldr_slash(self, interaction: discord.Interaction, limit: int = 50):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message("⏳ Slow down! (10s cooldown)", ephemeral=True)
        
        if limit > 200: 
            limit = 200
        
        await interaction.response.defer()
        
        history = [msg async for msg in interaction.channel.history(limit=limit)]
        history.reverse() 
        
        vip_role = get_vip_role_id(interaction.guild.id)
        formatted_text = self.format_history(history, vip_role)
        truncated_text = smart_truncate_history(formatted_text)
        
        lang = get_target_language(interaction.user.id, "English")
        
        data, used_model = await generate_summary(truncated_text, lang, interaction.guild.id)
        
        if not data:
            return await interaction.followup.send("❌ Failed to generate summary.")
            
        topic = data.get("topic", "Chat Summary")
        summary = data.get("summary", "No summary.")
        sentiment = data.get("sentiment", "neutral").lower()
        actions = data.get("actions", [])
        
        color = 0x95A5A6 
        if "happy" in sentiment: color = 0x2ECC71 
        elif "tense" in sentiment: color = 0xE74C3C 
        
        embed = discord.Embed(title=f"📝 TL;DR ({limit} messages)", description=summary, color=color)
        embed.set_author(name=topic)
        
        if actions:
            embed.add_field(name="Key Points", value="\n".join([f"• {a}" for a in actions[:5]]), inline=False)
            
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TLDRCog(bot))
