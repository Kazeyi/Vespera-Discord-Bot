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

    # --- ERROR HANDLER ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "⛔ **Access Denied:** Only the **Bot Owner** can use this command.",
                ephemeral=True
            )

    @app_commands.command(name="reload_genres", description="Hot-reload the genre map without restarting (Owner only)")
    @app_commands.check(is_bot_owner)
    async def reload_genres(self, interaction: discord.Interaction):
        """Clears the in-memory genre map cache so the next lookup re-reads from disk."""
        from cogs.utility_core.genre_mapper import reload_genre_map
        reload_genre_map()
        await interaction.response.send_message(
            "✅ Genre map reloaded from disk.", ephemeral=True
        )

    @app_commands.command(name="set_model", description="Change the AI model for this server (Owner Only)")
    @app_commands.describe(model_name="The full name of the model to use (e.g., models/gemini-2.5-pro)")
    @app_commands.check(is_bot_owner)
    async def set_model(self, interaction: discord.Interaction, model_name: str):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return
            
        import database
        database.save_mod_settings(interaction.guild.id, ai_model=model_name)
        
        embed = discord.Embed(
            title="🤖 Model Configuration Updated",
            description=f"The AI model for **{interaction.guild.name}** has been updated to:\n`{model_name}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))