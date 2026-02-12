import discord
from discord import app_commands
from discord.ext import commands
import psutil
import time

# --- CHECK: IS BOT OWNER? ---
async def is_bot_owner(interaction: discord.Interaction):
    # Checks if the user is the owner defined in Discord Dev Portal
    return await interaction.client.is_owner(interaction.user)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    def get_uptime(self):
        uptime_seconds = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

    @app_commands.command(name="status", description="Check VPS Health (Owner Only)")
    @app_commands.check(is_bot_owner)
    async def status(self, interaction: discord.Interaction):
        # 1. CPU Usage
        cpu_percent = psutil.cpu_percent()
        
        # 2. RAM Usage
        mem = psutil.virtual_memory()
        ram_used = mem.used / (1024 * 1024) 
        ram_total = mem.total / (1024 * 1024)
        ram_percent = mem.percent

        color = 0x00ff00
        if ram_percent > 85: color = 0xff0000
        elif ram_percent > 70: color = 0xffa500

        embed = discord.Embed(title="📊 System Diagnostics", color=color)
        embed.add_field(name="⏱️ Uptime", value=self.get_uptime(), inline=True)
        embed.add_field(name="📶 Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="🧠 RAM", value=f"**{ram_percent}%** ({int(ram_used)}/{int(ram_total)}MB)", inline=False)
        embed.add_field(name="⚡ CPU", value=f"**{cpu_percent}%**", inline=False)
        embed.set_footer(text="Vespera // Operational Efficiency: " + str(round(100 - ram_percent)) + "%")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
# ... [Existing code for /status command] ...

    # --- ERROR HANDLER (ADD THIS) ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "⛔ **Access Denied:** Only the **Bot Owner** can view system status.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminCog(bot))