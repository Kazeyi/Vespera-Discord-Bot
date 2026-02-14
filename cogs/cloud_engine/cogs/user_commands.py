"""
User Commands - Cloud provisioning commands for end users

These commands allow users to deploy infrastructure within their quotas.
All business logic is delegated to CloudOrchestrator.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

from ..core.orchestrator import CloudOrchestrator
from ..ui.lobby_view import DeploymentLobbyView
from cloud_database import CloudDatabase


class UserCommands(commands.Cog):
    """
    User-facing cloud provisioning commands
    
    Commands:
    - /cloud-deploy: Start a new deployment
    - /cloud-list: List your deployments
    - /cloud-quota: Check your quotas
    - /cloud-projects: List available projects
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = CloudDatabase()
        self.orchestrator = CloudOrchestrator(self.db)
    
    @app_commands.command(name="cloud-deploy", description="🚀 Deploy cloud infrastructure")
    @app_commands.describe(
        project="The cloud project to deploy to",
        provider="Cloud provider (GCP, AWS, or Azure)"
    )
    async def cloud_deploy(
        self,
        interaction: discord.Interaction,
        project: str,
        provider: Literal["gcp", "aws", "azure"] = "gcp"
    ):
        """
        Start a new cloud deployment
        
        This creates an interactive lobby with:
        - Add Resource button
        - Automatic terraform plan
        - Approve & Deploy button (enabled after plan)
        - Real-time apply output in Discord thread
        """
        await interaction.response.defer()
        
        # Check if user has access to project
        has_access = self.db.check_user_permission(
            interaction.user.id,
            project,
            'deploy'
        )
        
        if not has_access:
            await interaction.followup.send(
                f"❌ You don't have permission to deploy to project `{project}`.\n"
                f"Ask an admin to grant you access with `/cloud-grant`.",
                ephemeral=True
            )
            return
        
        # Start session
        session = await self.orchestrator.start_session(
            user_id=interaction.user.id,
            project_id=project,
            provider=provider.lower(),
            ttl_minutes=30
        )
        
        # Create deployment lobby view
        view = DeploymentLobbyView(
            session=session,
            orchestrator=self.orchestrator
        )
        
        # Build initial embed
        embed = view._build_embed()
        
        # Send lobby message
        message = await interaction.followup.send(
            embed=embed,
            view=view
        )
        
        # Trigger planning workflow
        await view.on_view_initialized(interaction)
    
    @app_commands.command(name="cloud-list", description="📋 List your deployments")
    @app_commands.describe(
        include_expired="Include expired sessions"
    )
    async def cloud_list(
        self,
        interaction: discord.Interaction,
        include_expired: bool = False
    ):
        """
        List all deployment sessions for the user
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get user sessions
        sessions = self.orchestrator.get_user_sessions(
            interaction.user.id,
            include_expired=include_expired
        )
        
        if not sessions:
            await interaction.followup.send(
                "You have no active deployments.",
                ephemeral=True
            )
            return
        
        # Build embed
        embed = discord.Embed(
            title=f"☁️ Your Cloud Deployments ({len(sessions)})",
            color=discord.Color.blue()
        )
        
        for session in sessions[:10]:  # Limit to 10
            status_emoji = {
                'draft': '📝',
                'planning': '⏳',
                'plan_ready': '✅',
                'applying': '🚀',
                'applied': '✅',
                'failed': '❌',
                'cancelled': '🛑'
            }
            
            emoji = status_emoji.get(session.state.value, '❓')
            
            value = (
                f"**State:** {emoji} {session.state.value.replace('_', ' ').title()}\n"
                f"**Provider:** {session.provider.upper()}\n"
                f"**Resources:** {len(session.resources)}\n"
                f"**Expires:** <t:{int(session.expires_at.timestamp())}:R>"
            )
            
            embed.add_field(
                name=f"{session.project_id} ({session.id[:8]})",
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cloud-quota", description="📊 Check your cloud quotas")
    @app_commands.describe(
        project="Project to check quotas for"
    )
    async def cloud_quota(
        self,
        interaction: discord.Interaction,
        project: str
    ):
        """
        Display quota information for a project
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get quota info
        quota_info = self.orchestrator.get_project_quota(project)
        
        if not quota_info:
            await interaction.followup.send(
                f"❌ Project `{project}` not found.",
                ephemeral=True
            )
            return
        
        # Build embed
        embed = discord.Embed(
            title=f"📊 Quotas for {project}",
            color=discord.Color.gold()
        )
        
        # Add quota fields
        for resource_type, quota in quota_info.items():
            limit = quota.get('limit', 'unlimited')
            used = quota.get('used', 0)
            
            if limit == 'unlimited':
                value = f"Used: {used} / ∞"
            else:
                percentage = (used / limit) * 100 if limit > 0 else 0
                bar = self._create_progress_bar(percentage)
                value = f"{bar} {used}/{limit} ({percentage:.0f}%)"
            
            embed.add_field(
                name=resource_type.replace('_', ' ').title(),
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cloud-projects", description="📁 List available cloud projects")
    async def cloud_projects(self, interaction: discord.Interaction):
        """
        List all cloud projects the user has access to
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get projects from database
        projects = self.db.list_user_projects(interaction.user.id)
        
        if not projects:
            await interaction.followup.send(
                "You don't have access to any cloud projects.\n"
                "Ask an admin to grant you access with `/cloud-grant`.",
                ephemeral=True
            )
            return
        
        # Build embed
        embed = discord.Embed(
            title="📁 Your Cloud Projects",
            description=f"You have access to {len(projects)} project(s)",
            color=discord.Color.blue()
        )
        
        for project in projects:
            project_id = project['project_id']
            provider = project.get('provider', 'gcp')
            permissions = project.get('permissions', [])
            
            value = (
                f"**Provider:** {provider.upper()}\n"
                f"**Permissions:** {', '.join(permissions)}"
            )
            
            embed.add_field(
                name=project_id,
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cloud-cancel", description="🛑 Cancel a deployment")
    @app_commands.describe(
        session_id="Session ID to cancel (from /cloud-list)"
    )
    async def cloud_cancel(
        self,
        interaction: discord.Interaction,
        session_id: str
    ):
        """
        Cancel an active deployment session
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get session
        session = self.orchestrator.get_session(session_id)
        
        if not session:
            await interaction.followup.send(
                "❌ Session not found or already expired.",
                ephemeral=True
            )
            return
        
        # Check if user owns the session
        if session.user_id != interaction.user.id:
            await interaction.followup.send(
                "❌ You can only cancel your own deployments.",
                ephemeral=True
            )
            return
        
        # Cancel session
        success = await self.orchestrator.cancel_session(session_id)
        
        if success:
            await interaction.followup.send(
                f"✅ Deployment `{session_id[:8]}` cancelled.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to cancel deployment. It may already be applying or completed.",
                ephemeral=True
            )
    
    def _create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """
        Create a text-based progress bar
        
        Example: [████████░░] 80%
        """
        filled = int((percentage / 100) * length)
        empty = length - filled
        
        return f"[{'█' * filled}{'░' * empty}]"


async def setup(bot: commands.Bot):
    """
    Setup function called by bot.load_extension()
    """
    await bot.add_cog(UserCommands(bot))
