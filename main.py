# --- START OF FILE main.py ---
import discord
from discord.ext import commands
from discord import app_commands
import os
import gc
import asyncio
from dotenv import load_dotenv

# Memory optimization
gc.set_threshold(400, 5, 5)  # Aggressive GC for low memory
gc.enable()

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Import memory optimizer
try:
    from memory_optimizer import memory_optimizer
    MEMORY_OPTIMIZATION_ENABLED = True
except:
    MEMORY_OPTIMIZATION_ENABLED = False
    print("⚠️ Memory optimizer not available")

# --- CONFIGURATION ---
# 1. Get your Server ID (Right Click Server Icon -> Copy ID)
# If you don't set this, you must type '!sync' manually.
TEST_GUILD_ID = None  # Example: 123456789012345678 or None

intents = discord.Intents.default()
intents.message_content = True  # REQUIRED: For TLDR, Translate, D&D AI analysis
intents.members = True           # REQUIRED: For D&D role-based access control

class ModularBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=intents,
            help_command=None,
            chunk_guilds_at_startup=False,  # Don't load all members at startup
            member_cache_flags=discord.MemberCacheFlags.none()  # Minimal member cache
        )
        self._cleanup_task = None

    async def setup_hook(self):
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write("--- Loading Cogs ---\n")
        print("--- Loading Cogs ---")
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py') and filename != "__init__.py":
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        msg = f"✅ Loaded: {filename}"
                        with open('/tmp/bot_debug.log', 'a') as f:
                            f.write(msg + "\n")
                        print(msg)
                    except Exception as e:
                        msg = f"❌ Failed to load {filename}: {e}"
                        with open('/tmp/bot_debug.log', 'a') as f:
                            f.write(msg + "\n")
                        print(msg)
        
        # AUTO SYNC LOGIC: Always sync globally for instant command availability
        try:
            synced = await self.tree.sync()
            print(f"🌍 Global Sync: {len(synced)} commands registered globally")
            print("   ℹ️ Commands available immediately in all servers")
        except Exception as e:
            print(f"⚠️ Sync warning: {e}")

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandNotFound):
            await interaction.response.send_message("⚠️ **Sync Issue:** Commands are updating. Please wait 1 minute or type `!sync`.", ephemeral=True)
        else:
            print(f"Tree Error: {error}")
            try: await interaction.response.send_message(f"❌ Error: {str(error)[:100]}", ephemeral=True)
            except: pass

    async def on_ready(self):
        print(f"🚀 Logged in as {self.user} (ID: {self.user.id})")
        print("--- Bot Ready ---")
        print("👉 If commands are missing, type '!sync' in the chat.")
        
        # Memory report
        if MEMORY_OPTIMIZATION_ENABLED:
            report = memory_optimizer.memory_report()
            print(f"💾 Memory: {report['memory_mb']:.1f}MB [{report['memory_status']}]")
        
        # Start background cleanup task
        if not self._cleanup_task:
            self._cleanup_task = self.loop.create_task(self._periodic_cleanup())
        
        await self.change_presence(
            activity=discord.Game(name="Use /help to understand better"),
            status=discord.Status.online
        )
    
    async def _periodic_cleanup(self):
        """Periodic memory cleanup (every 15 minutes)"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                await asyncio.sleep(900)  # 15 minutes
                
                if MEMORY_OPTIMIZATION_ENABLED:
                    memory_optimizer.cleanup_on_low_memory()
                else:
                    gc.collect()
                
                # Clear Discord.py cache
                self._connection.clear()
                
            except Exception as e:
                print(f"❌ Cleanup task error: {e}")
    
    async def close(self):
        """Cleanup on shutdown"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        if MEMORY_OPTIMIZATION_ENABLED:
            memory_optimizer.clear_all_caches()
        
        await super().close()

bot = ModularBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    """Manually force slash commands to appear."""
    msg = await ctx.send("🔄 Syncing...")
    try:
        # 1. Sync to the current server (Instant)
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        
        await msg.edit(content=f"✅ **Synced!** {len(synced)} commands detected.")
        print(f"Synced {len(synced)} commands to guild {ctx.guild.id}.")
    except Exception as e:
        await msg.edit(content=f"❌ Sync failed: {e}")


@bot.command()
@commands.has_permissions(administrator=True)
async def memory(ctx):
    """Check bot memory usage"""
    if not MEMORY_OPTIMIZATION_ENABLED:
        await ctx.send("⚠️ Memory optimizer not available")
        return
    
    report = memory_optimizer.memory_report()
    
    # Status emoji
    status_emoji = {
        'OK': '✅',
        'HIGH': '⚠️',
        'CRITICAL': '🚨'
    }.get(report['memory_status'], '❓')
    
    embed = discord.Embed(
        title=f"{status_emoji} Memory Status",
        color=discord.Color.green() if report['memory_status'] == 'OK' else discord.Color.orange()
    )
    
    embed.add_field(
        name="Current Usage",
        value=f"{report['memory_mb']:.1f} MB",
        inline=True
    )
    
    embed.add_field(
        name="Status",
        value=report['memory_status'],
        inline=True
    )
    
    embed.add_field(
        name="GC Collections",
        value=f"Gen0: {report['gc_count'][0]}, Gen1: {report['gc_count'][1]}, Gen2: {report['gc_count'][2]}",
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def cleanup(ctx):
    """Force memory cleanup"""
    msg = await ctx.send("🧹 Cleaning up memory...")
    
    before_mb = memory_optimizer.get_memory_mb() if MEMORY_OPTIMIZATION_ENABLED else 0
    
    if MEMORY_OPTIMIZATION_ENABLED:
        memory_optimizer.clear_all_caches()
        memory_optimizer.optimize_gc()
    else:
        gc.collect(2)
    
    # Clear Discord cache
    bot._connection.clear()
    
    after_mb = memory_optimizer.get_memory_mb() if MEMORY_OPTIMIZATION_ENABLED else 0
    freed = before_mb - after_mb
    
    await msg.edit(content=f"✅ **Cleanup Complete**\nFreed: {freed:.1f} MB\nCurrent: {after_mb:.1f} MB")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Error: DISCORD_TOKEN is missing from .env")
    else:
        bot.run(DISCORD_TOKEN)