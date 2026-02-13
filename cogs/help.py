import discord
from discord import app_commands
from discord.ext import commands
import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Attempt to import Personality, fallback gracefully if not found
try:
    from cogs.utility_core.personality import VesperaPersonality as VP
    COLORS = VP.Colors
except ImportError:
    class Defaults:
        PRIMARY = 0x2C2F33
        MYSTIC = 0x9B59B6
    COLORS = Defaults

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Access the Vespera Interface Manifest.")
    async def help_command(self, interaction: discord.Interaction):
        """Displays the main Vespera Help Interface."""
        
        # --- 1. The Header ---
        embed = discord.Embed(
            title="Vespera // The Silent Architect",
            description='"Order is not a suggestion; it is a requirement."',
            color=COLORS.PRIMARY
        )

        # --- 2. The Profile Summary ---
        embed.add_field(
            name="\u200b",
            value="Vespera is a high-tier intelligence designed for those who demand absolute control and crystalline clarity. She does not merely assist; she governs.",
            inline=False
        )

        # --- 3. Core Modules ---
        embed.add_field(
            name="🏁 Universal Lexicon",
            value="Sophisticated, real-time translation that captures nuance and intent across any border.\nUsage: `/translate`",
            inline=False
        )
        embed.add_field(
            name="⚗️ The Alchemical TL;DR",
            value="Absolute distillation of data. Vespera strips away the noise to deliver the core essence of any discourse.\nUsage: `/tldr`",
            inline=False
        )
        embed.add_field(
            name="🛡️ Sentinel Governance",
            value="An advanced moderation suite that anticipates disruption and enforces order with cold, surgical precision.\nUsage: `/mod`",
            inline=False
        )

        # --- 4. The Separation ---
        embed.add_field(
            name="\u200b",
            value="*Vespera is the quiet power behind the most refined environments. Efficiency is her language. Discipline is her law.*",
            inline=False
        )

        # --- 5. The Secret Hook (D&D) ---
        # We check if D&D is loaded/enabled to potentially hide this, but per request it's static
        embed.set_footer(
            text="There are whispers that within her cold logic lies the heart of a storyteller, waiting for the right key to unlock worlds of myth and dice."
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
