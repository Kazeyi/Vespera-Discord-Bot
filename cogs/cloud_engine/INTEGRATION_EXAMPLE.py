"""
Example integration of Cloud Engine v2.0 into your main.py

This shows how to load the cloud provisioning cogs and set up the system.
"""

import discord
from discord.ext import commands
import asyncio

# Your bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Bot is ready"""
    print(f'Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('------')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


async def load_extensions():
    """Load all cogs including cloud engine"""
    
    # Load your existing cogs
    extensions = [
        'cogs.dnd',           # Your D&D cog
        'cogs.moderator',      # Your moderation cog
        # ... other cogs ...
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f'✅ Loaded {ext}')
        except Exception as e:
            print(f'❌ Failed to load {ext}: {e}')
    
    # Load cloud engine cogs (NEW)
    cloud_extensions = [
        'cloud_engine.cogs.user_commands',   # User cloud commands
        'cloud_engine.cogs.admin_commands',  # Admin cloud commands
    ]
    
    for ext in cloud_extensions:
        try:
            await bot.load_extension(ext)
            print(f'✅ Loaded {ext}')
        except Exception as e:
            print(f'❌ Failed to load {ext}: {e}')


async def start_cleanup_service():
    """Start the session cleanup service"""
    from session_cleanup_service import SessionCleanupService
    
    cleanup_service = SessionCleanupService()
    asyncio.create_task(cleanup_service.start())
    print('✅ Session cleanup service started')


async def main():
    """Main entry point"""
    
    # Initialize database (run once)
    from cloud_database import CloudDatabase
    db = CloudDatabase()
    print('✅ Cloud database initialized')
    
    # Load extensions
    await load_extensions()
    
    # Start cleanup service
    await start_cleanup_service()
    
    # Start bot
    async with bot:
        await bot.start('YOUR_BOT_TOKEN_HERE')


if __name__ == '__main__':
    asyncio.run(main())


# ============================================================================
# ALTERNATIVE: Manual orchestrator usage (for custom workflows)
# ============================================================================

"""
If you want to use the orchestrator directly in your code:

from cogs.cloud_engine import CloudOrchestrator
from cloud_database import CloudDatabase

# In your cog or command
db = CloudDatabase()
orchestrator = CloudOrchestrator(db)

@bot.tree.command(name="custom-deploy")
async def custom_deploy(interaction: discord.Interaction, project: str):
    '''Custom deployment workflow'''
    
    # Start session
    session = await orchestrator.start_session(
        user_id=interaction.user.id,
        project_id=project,
        provider='gcp'
    )
    
    # Add resources programmatically
    orchestrator.add_resource(session.id, 'compute_vm', {
        'name': 'auto-generated-vm',
        'machine_type': 'e2-medium',
        'region': 'us-central1'
    })
    
    # Validate
    validation = await orchestrator.validate_session(session.id)
    
    if not validation['is_valid']:
        await interaction.response.send_message(
            f"Validation failed: {validation['violations']}",
            ephemeral=True
        )
        return
    
    # Run plan
    plan = await orchestrator.run_plan(session.id)
    
    if not plan.success:
        await interaction.response.send_message(
            f"Plan failed: {plan.errors}",
            ephemeral=True
        )
        return
    
    # Show plan and ask for confirmation
    embed = discord.Embed(
        title=f"Deployment Plan for {project}",
        description=f"Resources to add: {plan.resources_to_add}\\n"
                    f"Estimated cost: ${plan.monthly_cost:.2f}/month",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Auto-approve if cost is under $50/month
    if plan.monthly_cost < 50:
        success = await orchestrator.approve_and_apply(
            session.id,
            interaction.user.id
        )
        
        if success:
            await interaction.followup.send(
                "✅ Deployment started! Check logs for progress.",
                ephemeral=True
            )
"""


# ============================================================================
# EXAMPLE: Create test data for development
# ============================================================================

async def setup_test_data():
    """
    Create test projects and users for development
    Run this once to set up your test environment
    """
    from cloud_database import CloudDatabase
    
    db = CloudDatabase()
    
    # Create test projects
    projects = [
        ('dev-project', 'gcp', 'Development environment'),
        ('staging-project', 'aws', 'Staging environment'),
        ('prod-project', 'azure', 'Production environment'),
    ]
    
    for project_id, provider, description in projects:
        db.create_cloud_project(project_id, provider, description)
        print(f'✅ Created project: {project_id}')
        
        # Set quotas
        quotas = {
            'compute_vm': 10 if 'prod' not in project_id else 50,
            'database': 5,
            'vpc': 3,
            'storage_bucket': 20
        }
        
        for resource_type, limit in quotas.items():
            db.set_quota(project_id, resource_type, limit)
        
        print(f'   Set quotas for {project_id}')
    
    print('✅ Test data setup complete!')
    print('\\nNext steps:')
    print('1. Run your bot: python main.py')
    print('2. Grant yourself permissions: /cloud-grant @yourself dev-project deploy')
    print('3. Start deploying: /cloud-deploy project:dev-project provider:gcp')


# Run setup_test_data() if needed:
# asyncio.run(setup_test_data())
