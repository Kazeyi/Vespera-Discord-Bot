import asyncio
"""
==============================================================================
TRANSLATE COG - LAZY GLOSSARY OPTIMIZED VERSION
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
from database import save_user_language, get_target_language, save_user_style, get_user_global_style

from .utility_core.translation import (
    get_gemini_translation,
    smart_split,
    STYLE_THEMES
)
from .utility_core.personality import VesperaPersonality as VP
from .utility_core.genre_mapper import log_genre_suggestion

class TranslateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name="Translate", callback=self.translate_ctx)
        self.bot.tree.add_command(self.ctx_menu)
        self.user_cooldowns = {}
        self.processed_cache = {}
        self.temp_style_cache = {}
        
        self.clear_cache_task.start()
        self.garbage_collection_task.start()
    
    def cog_unload(self):
        self.clear_cache_task.cancel()
        self.garbage_collection_task.cancel()
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @tasks.loop(hours=1)
    async def clear_cache_task(self):
        """Clear caches every hour"""
        self.processed_cache.clear()
        self.temp_style_cache.clear()
        print("🧹 Translate cache cleared")

    @tasks.loop(minutes=30)
    async def garbage_collection_task(self):
        collected = gc.collect()
        if collected > 0:
            print(f"🗑️ Translate GC: {collected} objects freed")

    def is_rate_limited(self, user_id, cooldown=5):
        """Check user rate limit"""
        now = time.time()
        if user_id in self.user_cooldowns and now - self.user_cooldowns[user_id] < cooldown:
            return True
        self.user_cooldowns[user_id] = now
        return False

    @app_commands.command(name="subtitle", description="Translate text with specific tone")
    @app_commands.choices(style=[
        app_commands.Choice(name="👔 Formal",   value="Formal"),
        app_commands.Choice(name="🧢 Informal", value="Informal"),
        app_commands.Choice(name="⚡ Slang",    value="Slang/Chat"),
        app_commands.Choice(name="🎻 Lyrical",  value="Lyrical")
    ])
    @app_commands.choices(source_lang=[
        app_commands.Choice(name="Auto Detect", value="auto"),
        app_commands.Choice(name="Japanese",    value="Japanese"),
        app_commands.Choice(name="Chinese",     value="Chinese"),
        app_commands.Choice(name="Korean",      value="Korean"),
        app_commands.Choice(name="English",     value="English"),
        app_commands.Choice(name="Indonesian",  value="Indonesian")
    ])
    @app_commands.choices(genre=[
        app_commands.Choice(name="🎤 Upbeat / Rap",     value="upbeat_rap"),
        app_commands.Choice(name="🎸 Mid-tempo Rock",   value="mid_tempo_rock"),
        app_commands.Choice(name="🔥 Uplifting Anthem", value="uplifting_anthem"),
        app_commands.Choice(name="💙 Emotional Ballad", value="emotional_ballad"),
        app_commands.Choice(name="⚖️ Balanced (Auto)",  value="balanced"),
    ])
    async def subtitle(
        self,
        interaction: discord.Interaction,
        text: str,
        target: str,
        style: app_commands.Choice[str],
        source_lang: str = "auto",
        title: str = None,
        artist: str = None,
        genre: app_commands.Choice[str] = None,
    ):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message(VP.GENERAL['busy'], ephemeral=True)

        if len(text) < 1:
            return await interaction.response.send_message(VP.error("Input stream void."), ephemeral=True)

        if len(text) > 2000:
            return await interaction.response.send_message(VP.error("Data payload exceeds capacity (2000 chars)."), ephemeral=True)

        await interaction.response.defer()
        style_val = style.value
        genre_override = genre.value if genre else None
        in_rom, trans_text, trans_rom = await get_gemini_translation(
            text, target, style_val, interaction.guild.id, source_lang,
            title=title, artist=artist, genre_override=genre_override
        )
        
        theme = STYLE_THEMES.get(style_val, STYLE_THEMES["Slang/Chat"])
        icon = theme["icon"]
        color = theme["color"]
        
        romanization_part = f" ({trans_rom})" if trans_rom and trans_rom not in ["NA", "N/A"] else ""
        formatted_reply = f"Original: {text}\nTranslate ({target}) {icon}: {trans_text}{romanization_part}"
        if style_val.lower() == "lyrical":
            formatted_reply += "\n\n*📜 Translated using the Silent Architect's poetic philosophy.*"
        
        # Split reply into multiple messages if it exceeds Discord's length capacity
        reply_chunks = smart_split(formatted_reply, limit=1900)
        for chunk in reply_chunks:
            await interaction.followup.send(chunk)

    async def translate_ctx(self, interaction: discord.Interaction, message: discord.Message):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message("⏳ Slow down! (5s cooldown)", ephemeral=True)
        
        if not message.content:
            return await interaction.response.send_message("❌ No text to translate.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        lang = await asyncio.to_thread(get_target_language, interaction.user.id, "English")
        style = await asyncio.to_thread(get_user_global_style, interaction.user.id)
        
        in_rom, trans_text, trans_rom = await get_gemini_translation(
            message.content, lang, style, interaction.guild.id
        )
        
        theme = STYLE_THEMES.get(style, STYLE_THEMES["Slang/Chat"])
        icon = theme["icon"]
        color = theme["color"]
        
        romanization_part = f" ({trans_rom})" if trans_rom and trans_rom not in ["NA", "N/A"] else ""
        formatted_reply = f"Original: {message.content}\nTranslate ({lang}) {icon}: {trans_text}{romanization_part}"
        if style.lower() == "lyrical":
            formatted_reply += "\n\n*📜 Translated using the Silent Architect's poetic philosophy.*"
        
        # Split reply into multiple messages if it exceeds Discord's length capacity
        reply_chunks = smart_split(formatted_reply, limit=1900)
        for chunk in reply_chunks:
            await interaction.followup.send(chunk)

    @app_commands.command(name="setlanguage", description="Set your preferred language")
    async def set_lang(self, i: discord.Interaction, language: str):
        await asyncio.to_thread(save_user_language, i.user.id, language)
        await i.response.send_message(f"✅ Language preference updated to **{language}**.", ephemeral=True)

    @app_commands.command(name="setstyle", description="Set your default translation style")
    @app_commands.choices(style=[
        app_commands.Choice(name="👔 Formal", value="Formal"),
        app_commands.Choice(name="🧢 Informal", value="Informal"),
        app_commands.Choice(name="⚡ Slang", value="Slang/Chat"),
        app_commands.Choice(name="🎻 Lyrical", value="Lyrical")
    ])
    async def set_style(self, i: discord.Interaction, style: app_commands.Choice[str]):
        await asyncio.to_thread(save_user_style, i.user.id, style.value)
        theme = STYLE_THEMES.get(style.value, STYLE_THEMES["Slang/Chat"])
        await i.response.send_message(f"✅ Default translation style: **{theme['icon']} {style.name}**", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if self.bot.user and payload.user_id == self.bot.user.id:
            return
        
        for style_name, theme in STYLE_THEMES.items():
            if payload.emoji.name == theme["icon"]:
                self.temp_style_cache[(payload.user_id, payload.message_id)] = style_name
                channel = self.bot.get_channel(payload.channel_id)
                try:
                    msg = await channel.fetch_message(payload.message_id)
                    await msg.remove_reaction(payload.emoji, payload.member)
                except:
                    pass
                return

        flags = {
            "🇺🇸": "English", "🇬🇧": "English", "🇮🇩": "Indonesian",
            "🇯🇵": "Japanese", "🇰🇷": "Korean", "🇸🇦": "Arabic",
            "🇨🇳": "Chinese", "🇷🇺": "Russian", "🇫🇷": "French",
            "🇩🇪": "German", "🇪🇸": "Spanish", "🇹🇭": "Thai"
        }
        target = flags.get(payload.emoji.name)
        
        if target:
            if self.is_rate_limited(payload.user_id, cooldown=2):
                return
            
            cache_key = f"{payload.message_id}_{target}"
            if cache_key in self.processed_cache and (time.time() - self.processed_cache[cache_key] < 10):
                return
            self.processed_cache[cache_key] = time.time()
            
            ch = self.bot.get_channel(payload.channel_id)
            try:
                msg = await ch.fetch_message(payload.message_id)
            except:
                return
            
            if not msg.content:
                return
            
            # Get style preference
            final_style = self.temp_style_cache.pop(
                (payload.user_id, payload.message_id),
                await asyncio.to_thread(get_user_global_style, payload.user_id)
            )
            
            await ch.typing()
            in_rom, trans_text, trans_rom = await get_gemini_translation(
                msg.content, target, final_style, payload.guild_id
            )
            
            theme = STYLE_THEMES.get(final_style, STYLE_THEMES["Slang/Chat"])
            icon = theme["icon"]
            
            romanization_part = f" ({trans_rom})" if trans_rom and trans_rom not in ["NA", "N/A"] else ""
            final_msg = f"Original: {msg.content}\nTranslate ({target}) {icon}: {trans_text}{romanization_part}"
            if final_style.lower() == "lyrical":
                final_msg += "\n\n*📜 Translated using the Silent Architect's poetic philosophy.*"
            
            try:
                chunks = smart_split(final_msg, limit=1900)
                for chunk in chunks:
                    await msg.reply(chunk, mention_author=False)
                
                try:
                    await msg.remove_reaction(payload.emoji, payload.member)
                except:
                    pass
            except Exception as e:
                print(f"Translation reaction error: {e}")

    # ── /suggestgenre ─────────────────────────────────────────────────────────
    @app_commands.command(
        name="suggestgenre",
        description="Suggest a song→genre mapping for the Lyrical translator"
    )
    @app_commands.choices(genre=[
        app_commands.Choice(name="🎤 Upbeat / Rap",     value="upbeat_rap"),
        app_commands.Choice(name="🎸 Mid-tempo Rock",   value="mid_tempo_rock"),
        app_commands.Choice(name="🔥 Uplifting Anthem", value="uplifting_anthem"),
        app_commands.Choice(name="💙 Emotional Ballad", value="emotional_ballad"),
        app_commands.Choice(name="⚖️ Balanced (Auto)",  value="balanced"),
    ])
    async def suggest_genre(
        self,
        interaction: discord.Interaction,
        title: str,
        artist: str,
        genre: app_commands.Choice[str],
    ):
        """Log a user suggestion to data/genre_suggestions.log (not the live map)."""
        log_genre_suggestion(title, artist, genre.value, interaction.user.id)
        await interaction.response.send_message(
            f"✅ Thanks! Your suggestion **{artist} – {title}** → `{genre.value}` has been logged "
            f"and will be reviewed by an admin.",
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(TranslateCog(bot))
