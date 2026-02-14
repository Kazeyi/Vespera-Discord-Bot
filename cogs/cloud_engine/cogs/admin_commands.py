"""
Admin Commands - Cloud provisioning administration

These commands allow administrators to:
- Grant permissions to users
- Manage quotas
- Create projects
- View all deployments
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

from ..core.orchestrator import CloudOrchestrator
from cloud_database import CloudDatabase


class AdminCommands(commands.Cog):
    """
    Admin-only cloud provisioning commands
    
    Commands:
    - /cloud-grant: Grant permissions to a user
    - /cloud-revoke: Revoke permissions from a user
    - /cloud-create-project: Create a new cloud project
    - /cloud-set-quota: Set quotas for a project
    - /cloud-admin-list: List all deployments (admin view)
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = CloudDatabase()
        self.orchestrator = CloudOrchestrator(self.db)
    
    def is_admin(interaction: discord.Interaction) -> bool:
        """
        Check if user has administrator permission
        """
        return interaction.user.guild_permissions.administrator
    
    @app_commands.command(name="cloud-grant", description="🔑 Grant cloud permissions to a user")
    @app_commands.describe(
        user="User to grant permissions to",
        project="Cloud project to grant access to",
        permission="Permission level to grant"
    )
    @app_commands.check(is_admin)
    async def cloud_grant(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        project: str,
        permission: Literal["read", "deploy", "admin"]
    ):
        """
        Grant cloud permissions to a user (JIT access)
        
        This implements Just-In-Time access control.
        """
        await interaction.response.defer(ephemeral=True)
        
        # Grant permission
        success = self.db.grant_permission(
            user_id=user.id,
            project_id=project,
            permission=permission
        )
        
        if success:
            await interaction.followup.send(
                f"✅ Granted **{permission}** permission to {user.mention} for project `{project}`.",
                ephemeral=True
            )
            
            # Notify user
            try:
                await user.send(
                    f"🔑 You've been granted **{permission}** access to cloud project `{project}`!\n"
                    f"Use `/cloud-deploy` to start deploying infrastructure."
                )
            except discord.Forbidden:
                pass  # User has DMs disabled
        else:
            await interaction.followup.send(
                f"❌ Failed to grant permission. Project may not exist.",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-revoke", description="🚫 Revoke cloud permissions from a user")
    @app_commands.describe(
        user="User to revoke permissions from",
        project="Cloud project to revoke access to"
    )
    @app_commands.check(is_admin)
    async def cloud_revoke(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        project: str
    ):
        """
        Revoke cloud permissions from a user
        """
        await interaction.response.defer(ephemeral=True)
        
        # Revoke permission
        success = self.db.revoke_permission(
            user_id=user.id,
            project_id=project
        )
        
        if success:
            await interaction.followup.send(
                f"✅ Revoked permissions for {user.mention} on project `{project}`.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to revoke permission. User may not have access.",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-create-project", description="📁 Create a new cloud project")
    @app_commands.describe(
        project_id="Unique project identifier",
        provider="Cloud provider",
        description="Project description"
    )
    @app_commands.check(is_admin)
    async def cloud_create_project(
        self,
        interaction: discord.Interaction,
        project_id: str,
        provider: Literal["gcp", "aws", "azure"] = "gcp",
        description: str = ""
    ):
        """
        Create a new cloud project with default quotas
        """
        await interaction.response.defer(ephemeral=True)
        
        # Create project
        success = self.db.create_cloud_project(
            project_id=project_id,
            provider=provider,
            description=description
        )
        
        if success:
            # Set default quotas
            default_quotas = {
                'compute_vm': 10,
                'database': 5,
                'vpc': 3,
                'storage_bucket': 20
            }
            
            for resource_type, limit in default_quotas.items():
                self.db.set_quota(project_id, resource_type, limit)
            
            await interaction.followup.send(
                f"✅ Created cloud project `{project_id}` ({provider.upper()}).\n"
                f"**Default Quotas:**\n"
                f"- Compute VMs: 10\n"
                f"- Databases: 5\n"
                f"- VPCs: 3\n"
                f"- Storage Buckets: 20\n\n"
                f"Use `/cloud-set-quota` to adjust quotas.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to create project. Project ID may already exist.",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-set-quota", description="📊 Set quota limits for a project")
    @app_commands.describe(
        project="Cloud project",
        resource_type="Type of resource",
        limit="Maximum allowed (use -1 for unlimited)"
    )
    @app_commands.check(is_admin)
    async def cloud_set_quota(
        self,
        interaction: discord.Interaction,
        project: str,
        resource_type: Literal["compute_vm", "database", "vpc", "storage_bucket"],
        limit: int
    ):
        """
        Set quota limits for a project (FinOps cost control)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Set quota
        success = self.db.set_quota(
            project_id=project,
            resource_type=resource_type,
            limit=limit if limit >= 0 else None  # -1 = unlimited
        )
        
        if success:
            limit_text = "unlimited" if limit < 0 else str(limit)
            await interaction.followup.send(
                f"✅ Set quota for **{resource_type}** in `{project}` to **{limit_text}**.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to set quota. Project may not exist.",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-admin-list", description="📋 List all deployments (admin)")
    @app_commands.describe(
        project="Filter by project (optional)",
        state="Filter by state (optional)"
    )
    @app_commands.check(is_admin)
    async def cloud_admin_list(
        self,
        interaction: discord.Interaction,
        project: str = None,
        state: Literal["draft", "planning", "plan_ready", "applying", "applied", "failed"] = None
    ):
        """
        List all deployments across all users (admin view)
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get all sessions from database
        sessions = self.db.get_all_deployment_sessions(
            project_id=project,
            state=state
        )
        
        if not sessions:
            await interaction.followup.send(
                "No deployments found matching the criteria.",
                ephemeral=True
            )
            return
        
        # Build embed
        embed = discord.Embed(
            title=f"☁️ All Cloud Deployments ({len(sessions)})",
            color=discord.Color.purple()
        )
        
        if project:
            embed.description = f"**Project:** {project}"
        
        if state:
            embed.description = f"{embed.description or ''}\n**State:** {state}"
        
        for session_data in sessions[:15]:  # Limit to 15
            from ..models.session import CloudSession
            session = CloudSession.from_dict(session_data)
            
            user = self.bot.get_user(session.user_id)
            user_name = user.name if user else f"User {session.user_id}"
            
            value = (
                f"**User:** {user_name}\n"
                f"**Project:** {session.project_id}\n"
                f"**State:** {session.state.value.replace('_', ' ').title()}\n"
                f"**Resources:** {len(session.resources)}\n"
                f"**Created:** <t:{int(session.created_at.timestamp())}:R>"
            )
            
            embed.add_field(
                name=f"Session {session.id[:8]}",
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cloud-admin-cancel", description="🛑 Cancel any deployment (admin)")
    @app_commands.describe(
        session_id="Session ID to cancel"
    )
    @app_commands.check(is_admin)
    async def cloud_admin_cancel(
        self,
        interaction: discord.Interaction,
        session_id: str
    ):
        """
        Cancel any deployment session (admin override)
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
        
        # Cancel session
        success = await self.orchestrator.cancel_session(session_id)
        
        if success:
            await interaction.followup.send(
                f"✅ Admin cancelled deployment `{session_id}` for project `{session.project_id}`.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to cancel deployment.",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-stats", description="📊 View deployment statistics")
    @app_commands.check(is_admin)
    async def cloud_stats(self, interaction: discord.Interaction):
        """
        Display deployment statistics and metrics
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get statistics from database
        stats = self.db.get_deployment_statistics()
        
        # Build embed
        embed = discord.Embed(
            title="📊 Cloud Deployment Statistics",
            color=discord.Color.blue()
        )
        
        # Total deployments
        embed.add_field(
            name="Total Deployments",
            value=str(stats.get('total_deployments', 0)),
            inline=True
        )
        
        # Success rate
        total = stats.get('total_deployments', 0)
        successful = stats.get('successful_deployments', 0)
        success_rate = (successful / total * 100) if total > 0 else 0
        
        embed.add_field(
            name="Success Rate",
            value=f"{success_rate:.1f}%",
            inline=True
        )
        
        # Active sessions
        embed.add_field(
            name="Active Sessions",
            value=str(stats.get('active_sessions', 0)),
            inline=True
        )
        
        # Most active users
        top_users = stats.get('top_users', [])[:5]
        if top_users:
            user_list = "\n".join([
                f"<@{user_id}>: {count} deployments"
                for user_id, count in top_users
            ])
            embed.add_field(
                name="Top Users",
                value=user_list,
                inline=False
            )
        
        # Most deployed resources
        top_resources = stats.get('top_resources', [])[:5]
        if top_resources:
            resource_list = "\n".join([
                f"{resource_type}: {count}x"
                for resource_type, count in top_resources
            ])
            embed.add_field(
                name="Most Deployed Resources",
                value=resource_list,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """
    Setup function called by bot.load_extension()
    """
    await bot.add_cog(AdminCommands(bot))
