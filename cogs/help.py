import discord
from discord import app_commands
from discord.ext import commands
import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_dnd_config, get_mod_settings, get_vip_role_id, get_target_language
 

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def check_dnd_access(self, interaction):
        """Checks if user should see D&D commands based on DB config."""
        try:
            # 1. Admin Override
            if interaction.user.guild_permissions.manage_guild:
                return True

            # 2. Get Config from DB
            settings = get_dnd_config(interaction.guild.id)
            if not settings:
                return False

            # settings indices: 0=parent_ch, 4=role_id
            dnd_channel_id = settings[0]
            dnd_role_id = settings[4]

            # 3. Location Check
            if str(interaction.channel.id) == str(dnd_channel_id):
                return True
            if isinstance(interaction.channel, discord.Thread) and str(interaction.channel.parent_id) == str(dnd_channel_id):
                return True

            # 4. Role Check
            if dnd_role_id and dnd_role_id != "None":
                role = interaction.guild.get_role(int(dnd_role_id))
                if role and role in interaction.user.roles:
                    return True
                return False

            # 5. Public Access if no role set
            return True
        except:
            return False

    def check_mod_access(self, interaction):
        """Checks if user should see Moderation commands."""
        try:
            # Server owner or admins/managers always have access
            if interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator:
                return True

            # Check mod role from DB
            s = get_mod_settings(interaction.guild.id)
            if s and s[1] and interaction.user.get_role(int(s[1])):
                return True
            return False
        except:
            return False

    def check_translate_access(self, interaction):
        """Translate is available to most users; hide only if channel disallows commands (e.g., DMs blocked)."""
        try:
            if not interaction.guild:
                return False
            return True
        except:
            return False

    def check_tldr_access(self, interaction):
        """TL;DR is generally available but requires message-read permissions; only show if bot can read channel."""
        try:
            if not interaction.guild:
                return False
            # If bot lacks read history permission, hide to avoid confusion
            perms = interaction.channel.permissions_for(interaction.guild.me)
            return perms.read_message_history and perms.read_messages
        except:
            return False

    @app_commands.command(name="help", description="Access Vespera's protocols.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Vespera // The Silent Architect",
            description=(
                "**\"Order is not a suggestion; it is a requirement.\"**\n\n"
                "Vespera is a high-tier intelligence designed for those who demand absolute control and crystalline clarity. "
                "She does not merely assist; she governs.\n\n"
                "Efficiency is her language. Discipline is her law."
            ),
            color=0x2b2d42
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        # --- UNIVERSAL LEXICON ---
        embed.add_field(
            name="🌐 The Universal Lexicon",
            value=(
                "*Sophisticated, real-time translation that captures nuance and intent across any border.*\n\n"
                "• **Instant:** React with Flags (🇺🇸, 🇮🇩, 🇯🇵).\n"
                "• **Tonal Calibration:** React with a Style, *then* a Flag:\n"
                "   👔 **Formal** | 🧢 **Informal** | ⚡ **Slang** | 🎻 **Lyrical**\n"
                "• **Manual Input:** `/subtitle [text] [lang] [style]`\n"
                "• **Protocols:** `/setlanguage` & `/setstyle`."
            ),
            inline=False
        )

        # --- TL;DR ---
        # Show TL;DR only if the bot can read channel history (otherwise it's misleading)
        if self.check_tldr_access(interaction):
            vip_role = None
            try:
                vip_role = get_vip_role_id(interaction.guild.id)
            except:
                vip_role = None

            tldr_value = (
                "*Absolute distillation of data. Vespera clusters topics and highlights high-value contributors.*\n\n"
                "• **Command:** `/tldr [limit]` — Summarize recent chat (default limit 50).\n"
                "• **Context Menu:** Right-click a message -> Apps -> TL;DR for focused analysis.\n"
                "• **Cooldown:** ~10s per user to prevent spam.\n"
                "• **Permissions:** Bot requires Read Message History to summarize channel content.\n"
            )

            if vip_role:
                tldr_value += "• **VIPs:** High-value members are auto-tagged (🌟) in summaries when a VIP role is configured.\n"

            embed.add_field(name="⚗️ TL;DR (Summarization)", value=tldr_value, inline=False)

        # --- TRANSLATION ---
        if self.check_translate_access(interaction):
            trans_value = (
                "*Translate text with tone & style — built for nuance.*\n\n"
                "• **Command:** `/subtitle [text] [lang] [style]` — translate with optional tone.\n"
                "• **Context Menu:** Right-click a message -> Apps -> Translate.\n"
                "• **Styles:** Formal, Informal, Slang, Lyrical (use flags + style reactions).\n"
                "• **Preferences:** `/setlanguage` & `/setstyle` to set defaults.\n"
            )
            embed.add_field(name="🌍 Translation & Subtitles", value=trans_value, inline=False)

        # --- D&D ENGINE (Conditional Display) ---
        if self.check_dnd_access(interaction):
            # Build a D&D help block that reflects current saved state and the user's role
            try:
                cfg = get_dnd_config(interaction.guild.id)
            except:
                cfg = None

            has_save = False
            role_member = False
            if cfg:
                # cfg[2] is session summary; treat non-empty and not default as a save
                has_save = bool(cfg[2] and cfg[2] != "New Campaign Started.")
                dnd_role_id = cfg[4]
                if dnd_role_id and dnd_role_id != "None":
                    role = interaction.guild.get_role(int(dnd_role_id))
                    role_member = bool(role and role in interaction.user.roles)

            dnd_lines = ["*Unlocking the worlds of myth and dice.*\n\n"]

            # Initialization and basic commands (visible to users who passed check_dnd_access)
            dnd_lines.append("• **Initialization:** `/start_session` — opens the session lobby where host and players join.")
            dnd_lines.append("• **Import:** `/import_character` — import a character sheet or quick stats.")
            dnd_lines.append("• **Action:** `/do [action]` or use the in-lobby interface to take actions.")

            # Saved-session guidance
            if has_save:
                dnd_lines.append("")
                dnd_lines.append("• **Resume/Continue:** After `/start_session` the lobby will show **Continue** (Host only) to resume the saved game.")
                dnd_lines.append("• **Reset:** Use **Reset Campaign** in the lobby to discard the saved progress and start fresh.")
                dnd_lines.append("• **Note:** While a save exists, **Launch Session** and **⚙️ Settings** are locked — use **Continue** or **Reset**.")
            else:
                dnd_lines.append("")
                dnd_lines.append("• **Launch:** After `/start_session` the host may press **Launch Session** to start a new campaign.")
                dnd_lines.append("• **Settings:** Host can open **⚙️ Settings** in the lobby before launching to choose mode/tone/biome.")

            # Role-specific hints (if a D&D role is enforced, show how it affects access)
            if cfg and cfg[4] and cfg[4] != "None":
                dnd_lines.append("")
                dnd_lines.append("• **Access Control:** This server uses a D&D role to gate access. Only members with that role (or admins) will see the lobby and session commands.")
                if role_member:
                    dnd_lines.append("  • You have the D&D role — you can join sessions and use the interface.")
                else:
                    dnd_lines.append("  • You do not have the D&D role — ask an admin to grant it to participate.")

            dnd_lines.append("")
            dnd_lines.append("• **Combat & Fate:** `/roll_destiny` & `/roll_npc` exist for GMs and system use; the interface exposes combat controls when applicable.")

            embed.add_field(
                name="🗝️ The Secret Archives (Tabletop Engine)",
                value="\n".join(dnd_lines),
                inline=False
            )

        # --- SENTINEL GOVERNANCE ---
        if interaction.user.guild_permissions.manage_guild:
            embed.add_field(
                name="🛡️ Sentinel Governance",
                value=(
                    "*An advanced suite that anticipates disruption and enforces order with cold, surgical precision.*\n\n"
                    "• **Oversight:** `/setup_mod` (Configure alerts & auto-redirect).\n"
                    "• **Enforcement:** `/test_alert` (Debug permissions & test alerts).\n"
                    "• **Reputation:** `/my_rep` (Check toxicity scoring).\n"
                    "• **Configuration:** `/settings` (View Dashboard).\n"
                    "• **D&D:** `/setup_dnd` (Configure tabletop environment)."
                ),
                inline=False
            )

        # --- MODERATION (Moderator Role) ---
        if self.check_mod_access(interaction):
            mod_value = (
                "*Tools for moderators and server authorities to monitor and enforce community standards.*\n\n"
                "• **Setup:** `/setup_mod` — configure log channel, mod role, VIP role, and channel redirects.\n"
                "• **Alerts:** Automatic AI alerts trigger moderator notifications for spam/toxicity.\n"
                "• **Reputation:** `/my_rep` — view your toxicity score and history.\n"
                "• **Redirects:** Configure channel redirects to keep topics organized (via `/setup_mod`).\n"
                "• **Permissions:** By default, `/setup_mod` requires Manage Server; you can assign a Mod role for delegated access."
            )
            embed.add_field(name="🔧 Moderation Tools", value=mod_value, inline=False)

        # --- PRIME DIRECTIVE (OWNER ONLY) ---
        if await interaction.client.is_owner(interaction.user):
            embed.add_field(
                name="👑 Prime Directive",
                value=(
                    "• `/setmodel`: Adjust Neural Pathways (Select AI Model).\n"
                    "• `/status`: System Diagnostics."
                ),
                inline=False
            )

        # The Secret Hook
        embed.add_field(
            name="🔮 The Secret",
            value="*There are whispers that within her cold logic lies the heart of a storyteller, waiting for the right key to unlock worlds of myth and dice.*",
            inline=False
        )

        embed.set_footer(text="System Operational. Latency: " + str(round(self.bot.latency * 1000)) + "ms")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))