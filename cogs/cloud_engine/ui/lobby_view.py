"""
Discord UI Components - Deployment Lobby View

This is the interactive UI that users see when deploying infrastructure.
Implements the Plan-First workflow with real-time updates.
"""

import discord
from discord import ui
from typing import Optional, Callable
import asyncio

from ..models.session import CloudSession, DeploymentState
from .resource_modals import create_resource_modal


class DeploymentLobbyView(ui.View):
    """
    Interactive deployment lobby with Plan-First workflow
    
    Workflow:
    1. User clicks /cloud-deploy
    2. Lobby appears with "Planning..." state
    3. Terraform plan runs in background
    4. Plan results appear in embed
    5. "Approve & Deploy" button becomes enabled
    6. User clicks approve
    7. Terraform apply runs, output streams to thread
    """
    
    def __init__(
        self,
        session: CloudSession,
        orchestrator,
        on_plan_complete: Optional[Callable] = None,
        on_approve: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None
    ):
        super().__init__(timeout=1800)  # 30 minute timeout
        
        self.session = session
        self.orchestrator = orchestrator
        self.on_plan_complete = on_plan_complete
        self.on_approve = on_approve
        self.on_cancel = on_cancel
        
        # Initial state - buttons disabled until plan completes
        self.approve_button.disabled = True
        self.approve_button.style = discord.ButtonStyle.secondary
    
    async def on_view_initialized(self, interaction: discord.Interaction):
        """
        Called when view is first created
        
        Immediately starts the planning workflow
        """
        # Start planning in background
        asyncio.create_task(self._run_planning(interaction))
    
    async def _run_planning(self, interaction: discord.Interaction):
        """
        Background task to run terraform plan
        
        Updates the embed with plan results when complete
        """
        try:
            # Run plan
            plan_result = await self.orchestrator.run_plan(self.session.id)
            
            # Refresh session
            self.session = self.orchestrator.get_session(self.session.id)
            
            # Update embed
            embed = self._build_embed()
            
            # Enable approve button if plan succeeded
            if plan_result.success and self.session.can_approve:
                self.approve_button.disabled = False
                self.approve_button.style = discord.ButtonStyle.success
            
            # Update message
            await interaction.edit_original_response(embed=embed, view=self)
            
            # Call callback
            if self.on_plan_complete:
                await self.on_plan_complete(plan_result)
        
        except Exception as e:
            # Handle planning errors
            embed = discord.Embed(
                title="❌ Planning Failed",
                description=f"Failed to generate plan: {str(e)}",
                color=discord.Color.red()
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
    
    @ui.button(label="Approve & Deploy", style=discord.ButtonStyle.secondary, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        """
        Approve button - triggers terraform apply
        
        This creates a Discord thread for apply output streaming
        """
        await interaction.response.defer()
        
        # Trigger apply
        success = await self.orchestrator.approve_and_apply(
            self.session.id,
            interaction.user.id
        )
        
        if not success:
            await interaction.followup.send(
                "❌ Failed to start deployment. Session may be expired or invalid.",
                ephemeral=True
            )
            return
        
        # Create thread for apply output
        thread = await interaction.message.create_thread(
            name=f"Deploy {self.session.project_id}",
            auto_archive_duration=60
        )
        
        # Update embed
        embed = self._build_embed()
        await interaction.edit_original_response(embed=embed, view=self)
        
        # Start streaming apply output to thread
        asyncio.create_task(self._stream_apply_output(thread))
        
        # Disable buttons
        self.approve_button.disabled = True
        self.cancel_button.disabled = True
        await interaction.edit_original_response(view=self)
        
        # Call callback
        if self.on_approve:
            await self.on_approve(thread)
    
    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """
        Cancel button - cancels the deployment
        """
        await interaction.response.defer()
        
        # Cancel session
        success = await self.orchestrator.cancel_session(self.session.id)
        
        if success:
            embed = discord.Embed(
                title="🛑 Deployment Cancelled",
                description=f"Session `{self.session.id}` has been cancelled.",
                color=discord.Color.orange()
            )
            
            await interaction.edit_original_response(embed=embed, view=None)
        
        # Call callback
        if self.on_cancel:
            await self.on_cancel()
        
        # Stop the view
        self.stop()
    
    @ui.button(label="Add Resource", style=discord.ButtonStyle.primary, emoji="➕")
    async def add_resource_button(self, interaction: discord.Interaction, button: ui.Button):
        """
        Add Resource button - opens SELECT menu to choose resource type,
        then opens appropriate modal
        """
        # Show select menu for resource type
        view = ResourceTypeSelectView(self.session, self.orchestrator)
        
        await interaction.response.send_message(
            "Select resource type to add:",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: ui.Button):
        """
        Refresh button - updates the embed with current session state
        """
        # Refresh session
        self.session = self.orchestrator.get_session(self.session.id)
        
        if not self.session:
            await interaction.response.send_message(
                "❌ Session expired or not found.",
                ephemeral=True
            )
            return
        
        # Update embed
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _build_embed(self) -> discord.Embed:
        """
        Build the deployment lobby embed
        
        Shows:
        - Session info (project, provider, resources)
        - Current state
        - Plan results (if available)
        - Cost estimate (if available)
        """
        # Determine embed color based on state
        state_colors = {
            DeploymentState.DRAFT: discord.Color.blue(),
            DeploymentState.VALIDATING: discord.Color.gold(),
            DeploymentState.PLANNING: discord.Color.gold(),
            DeploymentState.PLAN_READY: discord.Color.green(),
            DeploymentState.APPROVED: discord.Color.purple(),
            DeploymentState.APPLYING: discord.Color.orange(),
            DeploymentState.APPLIED: discord.Color.dark_green(),
            DeploymentState.FAILED: discord.Color.red(),
            DeploymentState.CANCELLED: discord.Color.dark_grey(),
        }
        
        color = state_colors.get(self.session.state, discord.Color.default())
        
        # Build embed
        embed = discord.Embed(
            title=f"☁️ Cloud Deployment: {self.session.project_id}",
            description=f"**Provider:** {self.session.provider.upper()}\n**State:** {self.session.state.value.replace('_', ' ').title()}",
            color=color
        )
        
        # Add session info
        embed.add_field(
            name="Session ID",
            value=f"`{self.session.id[:8]}...`",
            inline=True
        )
        
        embed.add_field(
            name="Resources",
            value=f"{len(self.session.resources)} resources",
            inline=True
        )
        
        # Add time remaining
        if not self.session.is_expired:
            minutes_remaining = int(self.session.time_remaining_seconds / 60)
            embed.add_field(
                name="Time Remaining",
                value=f"{minutes_remaining} minutes",
                inline=True
            )
        
        # Add resource list
        if self.session.resources:
            resource_list = "\n".join([
                f"- **{r.type}**: {r.config.get('name', 'unnamed')}"
                for r in self.session.resources[:10]  # Limit to 10
            ])
            
            if len(self.session.resources) > 10:
                resource_list += f"\n... and {len(self.session.resources) - 10} more"
            
            embed.add_field(
                name="📦 Resources",
                value=resource_list,
                inline=False
            )
        
        # Add plan results (if available)
        if self.session.plan_result:
            plan = self.session.plan_result
            
            if plan.success:
                plan_summary = (
                    f"✅ **Plan Complete**\n"
                    f"➕ Add: {plan.resources_to_add}\n"
                    f"🔄 Change: {plan.resources_to_change}\n"
                    f"➖ Destroy: {plan.resources_to_destroy}"
                )
                
                embed.add_field(
                    name="📋 Terraform Plan",
                    value=plan_summary,
                    inline=False
                )
                
                # Add cost estimate
                if plan.estimated_cost_hourly > 0:
                    monthly_cost = plan.monthly_cost
                    embed.add_field(
                        name="💰 Estimated Cost",
                        value=f"${plan.estimated_cost_hourly:.2f}/hour\n${monthly_cost:.2f}/month",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="❌ Plan Failed",
                    value="\n".join(plan.errors[:3]),  # Show first 3 errors
                    inline=False
                )
        
        elif self.session.state == DeploymentState.PLANNING:
            embed.add_field(
                name="⏳ Planning in Progress",
                value="Running `terraform plan`...",
                inline=False
            )
        
        # Add footer
        embed.set_footer(text=f"Created at {self.session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return embed
    
    async def _stream_apply_output(self, thread: discord.Thread):
        """
        Stream terraform apply output to a Discord thread
        
        This provides real-time visibility into deployment progress
        """
        from ..core.terraform_runner import TerraformRunner
        
        # Create runner
        runner = TerraformRunner.create_for_session(self.session.id)
        
        # Send initial message
        await thread.send("🚀 **Starting deployment...**\n```\n```")
        
        # Stream output
        output_buffer = []
        message = None
        
        async for line in runner.stream_apply():
            output_buffer.append(line)
            
            # Update message every 10 lines or 2 seconds
            if len(output_buffer) >= 10:
                output_text = "\n".join(output_buffer[-50:])  # Keep last 50 lines
                
                if message:
                    try:
                        await message.edit(content=f"```\n{output_text}\n```")
                    except discord.errors.NotFound:
                        message = await thread.send(f"```\n{output_text}\n```")
                else:
                    message = await thread.send(f"```\n{output_text}\n```")
        
        # Send final summary
        self.session = self.orchestrator.get_session(self.session.id)
        
        if self.session.state == DeploymentState.APPLIED:
            await thread.send("✅ **Deployment completed successfully!**")
        else:
            await thread.send("❌ **Deployment failed. Check the output above for errors.**")


class ResourceTypeSelectView(ui.View):
    """
    View with select menu to choose resource type
    
    After selection, opens appropriate modal for that resource type.
    """
    
    def __init__(self, session: CloudSession, orchestrator):
        super().__init__(timeout=180)
        self.session = session
        self.orchestrator = orchestrator
    
    @ui.select(
        placeholder="Choose resource type to add...",
        options=[
            discord.SelectOption(
                label="Virtual Machine",
                value="compute_vm",
                description="Compute VM instance",
                emoji="🖥️"
            ),
            discord.SelectOption(
                label="Database",
                value="database",
                description="Managed database (PostgreSQL, MySQL, etc.)",
                emoji="🗄️"
            ),
            discord.SelectOption(
                label="VPC/Network",
                value="vpc",
                description="Virtual Private Cloud / Network",
                emoji="🌐"
            ),
            discord.SelectOption(
                label="Storage Bucket",
                value="storage_bucket",
                description="Object storage bucket (S3, GCS, Blob)",
                emoji="📦"
            ),
            discord.SelectOption(
                label="Load Balancer",
                value="load_balancer",
                description="Load balancer / traffic distributor",
                emoji="⚖️"
            ),
        ]
    )
    async def resource_type_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle resource type selection"""
        
        resource_type = select.values[0]
        
        # Create appropriate modal
        modal = create_resource_modal(
            resource_type,
            self.session.id,
            self.orchestrator,
            self.session.provider
        )
        
        if modal:
            await interaction.response.send_modal(modal)
        else:
            # Fallback to simple modal for unsupported types
            from .resource_modals import AddResourceModal
            modal = AddResourceModal(self.session, self.orchestrator)
            modal.resource_type.default = resource_type
            await interaction.response.send_modal(modal)


class AddResourceModal(ui.Modal, title="Add Cloud Resource"):
    """
    Modal for adding resources to a deployment session
    """
    
    resource_type = ui.TextInput(
        label="Resource Type",
        placeholder="compute_vm, database, vpc, etc.",
        max_length=50
    )
    
    resource_name = ui.TextInput(
        label="Resource Name",
        placeholder="my-server-01",
        max_length=100
    )
    
    machine_type = ui.TextInput(
        label="Machine Type / Size (if applicable)",
        placeholder="e2-medium, t3.micro, etc.",
        required=False,
        max_length=50
    )
    
    region = ui.TextInput(
        label="Region",
        placeholder="us-central1, us-east-1, eastus, etc.",
        required=False,
        max_length=50
    )
    
    def __init__(self, session: CloudSession, orchestrator):
        super().__init__()
        self.session = session
        self.orchestrator = orchestrator
    
    async def on_submit(self, interaction: discord.Interaction):
        """
        Handle modal submission
        """
        # Build config
        config = {
            'name': self.resource_name.value,
        }
        
        if self.machine_type.value:
            config['machine_type'] = self.machine_type.value
        
        if self.region.value:
            config['region'] = self.region.value
        
        # Add resource
        success = self.orchestrator.add_resource(
            self.session.id,
            self.resource_type.value,
            config
        )
        
        if success:
            await interaction.response.send_message(
                f"✅ Added **{self.resource_type.value}**: `{self.resource_name.value}`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to add resource. Session may be locked or expired.",
                ephemeral=True
            )
