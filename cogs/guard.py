"""
cogs/guard.py — Vespera Rate Guard Admin Commands
===================================================
Provides the /guard slash command group for the bot owner.

All subcommands are gated behind BOT_OWNER_ID in .env —
mathematically inaccessible to anyone else, even server admins.
"""

import os
import asyncio
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rate_guard import (
    admin_get_stats,
    admin_ban,
    admin_unban,
    admin_whitelist,
    admin_un_whitelist,
    admin_clear_strikes,
)

_OWNER_ID: str | None = os.getenv("BOT_OWNER_ID")


def _is_owner(interaction: discord.Interaction) -> bool:
    return _OWNER_ID is not None and str(interaction.user.id) == _OWNER_ID


class GuardCog(commands.Cog):
    """Rate Guard admin commands (/guard)"""

    guard_group = app_commands.Group(
        name="guard",
        description="Rate Guard admin panel — owner only"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # /guard stats
    # ------------------------------------------------------------------
    @guard_group.command(name="stats", description="Show API usage dashboard")
    async def guard_stats(self, interaction: discord.Interaction):
        """Display today's usage metrics, active bans, and recent strikers."""
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        stats = await asyncio.to_thread(admin_get_stats)

        embed = discord.Embed(
            title="🛡️ Rate Guard — Usage Dashboard",
            description=f"Snapshot as of <t:{int(time.time())}:R>",
            color=0x5865F2
        )

        # Total calls today
        embed.add_field(
            name="📊 Total API Calls (24h)",
            value=f"**{stats['total_today']:,}**",
            inline=False
        )

        # Top users
        if stats["top_users"]:
            top_lines = "\n".join(
                f"`{uid}` — **{calls:,}** calls"
                for uid, calls in stats["top_users"]
            )
        else:
            top_lines = "*No data yet*"
        embed.add_field(name="🏆 Top Users (24h)", value=top_lines, inline=False)

        # Recent strikers
        if stats["recent_strikes"]:
            strike_lines = "\n".join(
                f"`{uid}` — **{s}** strikes (last hour)"
                for uid, s in stats["recent_strikes"]
            )
        else:
            strike_lines = "*No strikes in the last hour*"
        embed.add_field(name="⚡ Recent Strikers", value=strike_lines, inline=False)

        # Active bans
        if stats["active_bans"]:
            ban_lines = "\n".join(
                f"`{uid}` — <t:{int(exp)}:R> · {reason[:40]} · {sc} strikes"
                for uid, exp, reason, sc in stats["active_bans"]
            )
        else:
            ban_lines = "*No active bans*"
        embed.add_field(name="🚫 Active Bans", value=ban_lines, inline=False)

        embed.set_footer(text="rate_guard.db • metadata only — no content logged")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /guard ban
    # ------------------------------------------------------------------
    @guard_group.command(name="ban", description="Manually ban a user from using the bot")
    @app_commands.describe(
        user_id="Discord user ID to ban",
        hours="Ban duration in hours (default: 24)",
        reason="Reason for the ban"
    )
    async def guard_ban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        hours: int = 24,
        reason: str = "manual ban by owner"
    ):
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await asyncio.to_thread(admin_ban, user_id, hours, reason)

        embed = discord.Embed(
            title="🚫 User Banned",
            color=0xE74C3C
        )
        embed.add_field(name="User ID", value=f"`{user_id}`", inline=True)
        embed.add_field(name="Duration", value=f"{hours} hours", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Use /guard unban to lift early.")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /guard unban
    # ------------------------------------------------------------------
    @guard_group.command(name="unban", description="Lift an active ban from a user")
    @app_commands.describe(user_id="Discord user ID to unban")
    async def guard_unban(self, interaction: discord.Interaction, user_id: str):
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        removed = await asyncio.to_thread(admin_unban, user_id)

        if removed:
            await interaction.followup.send(
                f"✅ Ban lifted for `{user_id}`. They can use the bot again.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ No active ban found for `{user_id}`.", ephemeral=True
            )

    # ------------------------------------------------------------------
    # /guard whitelist
    # ------------------------------------------------------------------
    @guard_group.command(name="whitelist", description="Whitelist a user to bypass all rate limits")
    @app_commands.describe(user_id="Discord user ID to whitelist")
    async def guard_whitelist(self, interaction: discord.Interaction, user_id: str):
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await asyncio.to_thread(admin_whitelist, user_id)

        await interaction.followup.send(
            f"✅ `{user_id}` is now whitelisted — rate limits bypassed permanently.\n"
            f"Use `/guard unwhitelist` to remove.",
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /guard unwhitelist
    # ------------------------------------------------------------------
    @guard_group.command(name="unwhitelist", description="Remove a user from the whitelist")
    @app_commands.describe(user_id="Discord user ID to remove from whitelist")
    async def guard_unwhitelist(self, interaction: discord.Interaction, user_id: str):
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        removed = await asyncio.to_thread(admin_un_whitelist, user_id)

        if removed:
            await interaction.followup.send(
                f"✅ `{user_id}` removed from whitelist — rate limits now apply.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ `{user_id}` was not on the whitelist.", ephemeral=True
            )

    # ------------------------------------------------------------------
    # /guard clearstrikes
    # ------------------------------------------------------------------
    @guard_group.command(name="clearstrikes", description="Clear all strikes for a user")
    @app_commands.describe(user_id="Discord user ID to clear strikes for")
    async def guard_clearstrikes(self, interaction: discord.Interaction, user_id: str):
        if not _is_owner(interaction):
            await interaction.response.send_message(
                "🔒 This command is restricted to the bot owner.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await asyncio.to_thread(admin_clear_strikes, user_id)

        await interaction.followup.send(
            f"✅ Strike history cleared for `{user_id}`.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GuardCog(bot))
