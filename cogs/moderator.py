"""
==============================================================================
MODERATOR COG - RAM-OPTIMIZED VERSION
==============================================================================
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import time
import json
import re
import os
import sys
import gc
from collections import defaultdict
from dotenv import load_dotenv
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DB_FILE, get_mod_settings, get_server_model_name, get_target_language

from .utility_core.moderator import (
    enable_wal_mode,
    ensure_mod_tables,
    get_lightweight_context,
    log_message_to_context,
    analyze_content,
    update_rep,
    save_settings,
    DEFAULT_MODEL
)
from .utility_core.personality import VesperaPersonality as VP

load_dotenv()

async def is_bot_owner(interaction: discord.Interaction):
    return await interaction.client.is_owner(interaction.user)

class ModeratorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Lightweight spam detection (RAM)
        self.spam_check = defaultdict(lambda: [])
        self.media_spam_tracker = defaultdict(lambda: [])
        self.gaming_stack = defaultdict(lambda: {'score': 0, 'last_msg': 0})
        
        self.processed_cache = {}
        
        ensure_mod_tables()
        enable_wal_mode()
        
        self.cleanup_task.start()
        self.garbage_collection_task.start()
    
    def cog_unload(self):
        self.cleanup_task.cancel()
        self.garbage_collection_task.cancel()

    @tasks.loop(hours=1)
    async def cleanup_task(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cutoff = time.time() - (24 * 3600)
        cursor.execute("DELETE FROM message_context_log WHERE timestamp < ?", (cutoff,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            print(f"🧹 Cleaned up {deleted} old context messages")
        
        now = time.time()
        for user_id in list(self.spam_check.keys()):
            self.spam_check[user_id] = [t for t in self.spam_check[user_id] if now - t < 60]
            if not self.spam_check[user_id]:
                del self.spam_check[user_id]
        
        for user_id in list(self.media_spam_tracker.keys()):
            self.media_spam_tracker[user_id] = [t for t in self.media_spam_tracker[user_id] if now - t < 120]
            if not self.media_spam_tracker[user_id]:
                del self.media_spam_tracker[user_id]
    
    @tasks.loop(minutes=30)
    async def garbage_collection_task(self):
        collected = gc.collect()
        if collected > 0:
            print(f"🗑️ Mod GC: {collected} objects freed")

    async def trigger_mod_alert(self, message, severity, reason, log_id, role_id, title, action_rec):
        if "Shadow" not in title and "Spam" not in title:
            if message.id in self.processed_cache:
                return
            self.processed_cache[message.id] = True
        
        try:
            cid = int(log_id)
            ch = self.bot.get_channel(cid)
            if not ch:
                ch = await self.bot.fetch_channel(cid)
        except:
            return

        color = 0xF1C40F
        if severity >= 5: color = 0xE67E22
        if severity >= 8: color = 0x992D22
        
        embed = discord.Embed(title=title, color=color)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.add_field(name="Severity", value=f"**{severity}/10**", inline=True)
        embed.add_field(name="User", value=message.author.mention, inline=True)
        embed.add_field(name="🤖 Vespera Protocol", value=f"`{action_rec}`", inline=False)
        clean = message.content[:1000].replace("||", "")
        embed.add_field(name="Message (Hidden)", value=f"||```\n{clean}\n```||", inline=False)
        embed.add_field(name="AI Analysis", value=f"*{reason}*", inline=False)
        embed.add_field(name="Action", value=f"[Jump]({message.jump_url})", inline=False)
        try:
            content = f"<@&{role_id}>" if role_id else None
            await ch.send(content=content, embed=embed)
        except:
            pass

    async def handle_redirect(self, message, target_id, reason, user_id):
        if not target_id or str(message.channel.id) == str(target_id):
            return
        ch = self.bot.get_channel(int(target_id))
        lang_pref = get_target_language(user_id, "English")
        msg_content = f"⚠️ **Redirect: {reason}**\nThis topic belongs in {ch.mention}. Please continue there."
        if "indonesia" in lang_pref.lower() or "bahasa" in lang_pref.lower():
            msg_content = f"⚠️ **Pengalihan: {reason}**\nTopik ini seharusnya dibahas di {ch.mention}. Silakan lanjut di sana ya."
        if ch:
            await message.reply(msg_content, delete_after=15)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        log_message_to_context(
            guild_id=str(message.guild.id),
            channel_id=str(message.channel.id),
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            content=message.content
        )
        
        now = time.time()
        self.spam_check[message.author.id].append(now)
        self.spam_check[message.author.id] = self.spam_check[message.author.id][-5:]
        
        if len(self.spam_check[message.author.id]) == 5:
            if now - self.spam_check[message.author.id][0] < 3:
                await message.channel.send(f"{message.author.mention} ⚠️ Slow down!", delete_after=5)
                update_rep(message.author.id, message.guild.id, 2)

        if message.attachments or "http" in message.content:
            self.media_spam_tracker[message.author.id].append(now)
            self.media_spam_tracker[message.author.id] = self.media_spam_tracker[message.author.id][-4:]
            
            if len(self.media_spam_tracker[message.author.id]) >= 4 and \
               now - self.media_spam_tracker[message.author.id][0] < 60:
                if update_rep(message.author.id, message.guild.id, 5) >= 15:
                    s = get_mod_settings(message.guild.id)
                    if s and s[0] and s[1]:
                        await self.trigger_mod_alert(message, 5, "Media Spam Flood.", s[0], s[1],
                                                      "⚠️ Media Spam Alert", "Timeout (1h)")
                    self.media_spam_tracker[message.author.id].clear()

        if len(message.content) < 4:
            return

        s = get_mod_settings(message.guild.id)
        if not s or not s[0]:
            return
        
        current_channel_type = "General"
        if s[2] and str(message.channel.id) == str(s[2]):
            current_channel_type = "POLITICS"
        elif s[4] and str(message.channel.id) == str(s[4]):
            current_channel_type = "GAMING"
        elif s[3] and str(message.channel.id) == str(s[3]):
            current_channel_type = "NSFW"
        elif message.channel.is_nsfw():
            current_channel_type = "NSFW"

        context = get_lightweight_context(
            guild_id=str(message.guild.id),
            channel_id=str(message.channel.id),
            limit=5
        )
        
        server_context = s[6] if s[6] else "General Gaming"
        cat, sev, reason, action_rec = await analyze_content(
            message.content,
            context,
            server_context,
            message.guild.id,
            current_channel_type
        )

        if cat == "TOXIC":
            if sev > 3:
                new_score = update_rep(message.author.id, message.guild.id, sev)
                if sev >= 7:
                    await self.trigger_mod_alert(message, sev, reason, s[0], s[1], "🚨 High Toxicity", action_rec)
                elif new_score >= 20:
                    await self.trigger_mod_alert(message, sev, reason, s[0], s[1],
                                                  "⚠️ Shadow Alert (Pattern)", "Monitor / Timeout")
                    update_rep(message.author.id, message.guild.id, -10)
        
        elif cat == "GAMING":
            if current_channel_type != "GAMING" and s[4]:
                stack = self.gaming_stack[message.author.id]
                if time.time() - stack['last_msg'] > 300:
                    stack['score'] = 0
                stack['score'] += sev
                stack['last_msg'] = time.time()
                if sev >= 5 or stack['score'] >= 15:
                    await self.handle_redirect(message, s[4], "Gaming Discussion", message.author.id)
                    stack['score'] = 0
        else:
            if message.author.id in self.gaming_stack:
                self.gaming_stack[message.author.id]['score'] = max(0,
                    self.gaming_stack[message.author.id]['score'] - 2)

        if cat == "POLITICS" and sev >= 4 and current_channel_type != "POLITICS":
            await self.handle_redirect(message, s[2], "Politics", message.author.id)
        elif cat == "NSFW" and sev >= 4 and current_channel_type != "NSFW":
            await self.handle_redirect(message, s[3], "NSFW Content", message.author.id)

    @app_commands.command(name="setup_mod", description="Configure Moderation")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_mod(self, i: discord.Interaction,
                        log_channel: discord.TextChannel = None,
                        mod_role: discord.Role = None,
                        context: str = None,
                        vip_role: discord.Role = None,
                        politics_channel: discord.TextChannel = None,
                        nsfw_channel: discord.TextChannel = None,
                        gaming_channel: discord.TextChannel = None):
        if not any([log_channel, mod_role, context, vip_role, politics_channel, nsfw_channel, gaming_channel]):
            await i.response.send_message("❌ You must select at least one option!", ephemeral=True)
            return
        
        kwargs = {}
        if log_channel: kwargs['log_channel'] = log_channel
        if mod_role: kwargs['mod_role'] = mod_role
        if context: kwargs['context'] = context
        if vip_role: kwargs['vip_role'] = vip_role
        if politics_channel: kwargs['politics_channel'] = politics_channel
        if nsfw_channel: kwargs['nsfw_channel'] = nsfw_channel
        if gaming_channel: kwargs['gaming_channel'] = gaming_channel
        
        save_settings(i.guild.id, **kwargs)
        
        await i.response.send_message("✅ **Moderation Configuration Updated!**", ephemeral=True)

    @app_commands.command(name="my_rep", description="Check your reputation score")
    async def my_rep(self, i: discord.Interaction):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT toxicity_score, last_offense_time FROM user_reputation WHERE user_id=? AND guild_id=?",
                  (str(i.user.id), str(i.guild.id)))
        res = c.fetchone()
        conn.close()
        
        final_score = 0
        if res:
            score, last_time = res
            hours = (time.time() - last_time) / 3600
            decay = int(hours * 2)
            final_score = max(0, score - decay)
        
        color = 0x00ff00
        status = "✅ Good Citizen"
        if final_score > 10:
            color = 0xffa500
            status = "⚠️ Caution"
        if final_score > 18:
            color = 0xff0000
            status = "🚨 Critical Risk"
        
        embed = discord.Embed(title=f"🛡️ Reputation: {i.user.name}", color=color)
        embed.add_field(name="Toxicity Score", value=f"**{final_score}/20**", inline=False)
        embed.add_field(name="Status", value=status, inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setmodel", description="Choose AI Model (Bot Owner Only)")
    @app_commands.check(is_bot_owner)
    @app_commands.choices(model=[
        app_commands.Choice(name="🔹 Gemma 3 27B-IT (Default)", value="models/gemma-3-27b-it"),
        app_commands.Choice(name="⚡ Gemini 2.0 Flash Lite", value="models/gemini-2.0-flash-lite"),
        app_commands.Choice(name="🧠 Gemini 2.5 Flash Lite", value="models/gemini-2.5-flash-lite"),
        app_commands.Choice(name="🚀 Gemini 3.0 Flash Preview", value="models/gemini-3-flash-preview")
    ])
    async def setmodel(self, interaction: discord.Interaction, model: app_commands.Choice[str]):
        save_settings(interaction.guild.id, model=model.value)
        await interaction.response.send_message(f"✅ updated to **{model.name}**!", ephemeral=True)

    @app_commands.command(name="settings", description="View Dashboard")
    @app_commands.default_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction):
        s = get_mod_settings(interaction.guild.id)
        if not s:
            return await interaction.response.send_message("Not configured.", ephemeral=True)
        log_id, role_id, pol_id, nsfw_id, game_id, vip_id, context, model = s
        
        embed = discord.Embed(title="🎛️ Dashboard", color=0x3498db)
        embed.add_field(name="Model", value=model if model else DEFAULT_MODEL, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="test_alert", description="Debug: Force a manual alert")
    @app_commands.default_permissions(administrator=True)
    async def test_alert(self, interaction: discord.Interaction):
        settings = get_mod_settings(interaction.guild.id)
        if not settings:
            return await interaction.response.send_message("❌ Not configured", ephemeral=True)
        log_id = settings[0]
        if not log_id: return await interaction.response.send_message("❌ No log channel", ephemeral=True)
        try:
             ch = self.bot.get_channel(int(log_id))
             await ch.send("🔔 Test Alert")
             await interaction.response.send_message("Sent", ephemeral=True)
        except:
             await interaction.response.send_message("Error", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModeratorCog(bot))
