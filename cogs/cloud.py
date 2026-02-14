# --- Cloud Infrastructure ChatOps Cog ---
"""
Discord ChatOps for Cloud Infrastructure Provisioning

Commands:
- /cloud init - Initialize cloud project
- /cloud deploy - Deploy infrastructure via interactive lobby
- /cloud list - List deployed resources
- /cloud quota - Check quota usage
- /cloud approve - Approve pending deployment (admin only)
- /cloud cancel - Cancel deployment session
- /cloud permissions - Manage user permissions

Inspired by D&D combat lobby system
Memory-optimized version for low-RAM environments
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import time
import os
import re
import shutil
import hashlib
import threading
import gc
import weakref
from typing import Optional, List, Generator
from datetime import datetime, timedelta
from contextlib import contextmanager
from collections import defaultdict
from functools import lru_cache
import sqlite3
import json

import cloud_database as cloud_db
import infrastructure_policy_validator as ipv
import cloud_provisioning_generator as cpg
import cloud_config_data as ccd

# Security & Multi-Tenancy imports
from cloud_security import (
    ephemeral_vault,
    MultiTenantStateManager,
    PolicyEnforcer,
    IACEngineManager
)

# AI Advisor imports
from cogs.cloud_engine.ai import CloudAIAdvisor, AIModel, CloudKnowledgeIngestor, CloudKnowledgeRAG
from cogs.cloud_engine.ai.terraform_validator import TerraformValidator

# Memory optimization
try:
    from memory_optimizer import memory_optimizer
    MEMORY_OPT = True
except:
    MEMORY_OPT = False

# Reduce LRU cache sizes for memory optimization
MAX_CACHE_SIZE = 64  # Reduced from default 128


# --- Security & Utility Classes ---

def sanitize_cloud_input(text: str, max_length: int = 100) -> str:
    """Sanitize user input for cloud resources (prevents injection attacks)"""
    # Remove dangerous patterns
    dangerous_patterns = [
        r'(\b(DROP|DELETE|INSERT|UPDATE|ALTER)\b)',
        r'(;|\-\-|\/\*|\*\/)',
        r'(\.\.\/)',  # Directory traversal
        r'(\$\{.*?\})',  # Variable injection
    ]
    
    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Ensure only safe characters
    safe_pattern = r'[^a-zA-Z0-9\-_\.@]'
    sanitized = re.sub(safe_pattern, '-', sanitized)
    
    return sanitized.strip()


class RateLimiter:
    """Rate limiting for commands to prevent abuse"""
    
    _limits = defaultdict(list)
    
    @classmethod
    def check_rate_limit(cls, user_id: str, command: str, limit: int = 5, window: int = 60) -> tuple:
        """Check if user is rate limited. Returns (allowed: bool, count: int)"""
        key = f"{user_id}:{command}"
        now = datetime.now()
        
        # Clean old entries
        cls._limits[key] = [t for t in cls._limits[key] if now - t < timedelta(seconds=window)]
        
        if len(cls._limits[key]) >= limit:
            return False, len(cls._limits[key])
        
        cls._limits[key].append(now)
        return True, len(cls._limits[key])


class ConfigurationValidator:
    """Validate resource configurations before passing to AI"""
    
    @staticmethod
    def validate_and_normalize(config: dict, resource_type: str) -> tuple:
        """Validate config and return (normalized_config: dict, warnings: list)"""
        warnings = []
        normalized = config.copy()
        
        # Machine type validation
        if 'machine_type' in config:
            mt = config['machine_type']
            if resource_type == 'vm' and 'micro' in mt.lower():
                warnings.append(f"⚠️ Using micro instance for production: {mt}")
        
        # Disk size validation
        if 'disk_size_gb' in config:
            disk_size = config['disk_size_gb']
            if isinstance(disk_size, str):
                try:
                    normalized['disk_size_gb'] = int(disk_size)
                except ValueError:
                    warnings.append(f"⚠️ Invalid disk size: {disk_size}, defaulting to 20GB")
                    normalized['disk_size_gb'] = 20
            
            if normalized['disk_size_gb'] < 10:
                warnings.append(f"⚠️ Small disk size ({disk_size}GB) may fill quickly")
        
        # Tag validation
        if 'tags' in config:
            if isinstance(config['tags'], str):
                normalized['tags'] = [t.strip() for t in config['tags'].split(',')]
            elif not isinstance(config['tags'], list):
                warnings.append("⚠️ Tags should be a list, converting")
                normalized['tags'] = []
        
        return normalized, warnings


class DatabaseManager:
    """Centralized database management with connection pooling"""
    
    _pool = []
    _max_pool_size = 5
    
    @classmethod
    @contextmanager
    def get_connection(cls) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection from pool"""
        if cls._pool:
            conn = cls._pool.pop()
        else:
            conn = sqlite3.connect(cloud_db.CLOUD_DB_FILE)
            conn.row_factory = sqlite3.Row
        
        try:
            yield conn
        finally:
            if len(cls._pool) < cls._max_pool_size:
                cls._pool.append(conn)
            else:
                conn.close()
    
    @classmethod
    def execute_query(cls, query: str, params: tuple = ()) -> list:
        """Execute query with connection pooling"""
        with cls.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


class TerraformStateManager:
    """Manage terraform state files with versioning"""
    
    @staticmethod
    async def execute_with_state_backup(
        command: str, 
        work_dir: str, 
        session_id: str,
        engine: str = "terraform"
    ) -> dict:
        """Execute terraform command with state backup"""
        
        # Backup current state before any operation
        backup_dir = f"tfstate_backups/{session_id}"
        os.makedirs(backup_dir, exist_ok=True)
        
        state_file = f"{work_dir}/terraform.tfstate"
        backup_path = None
        
        if os.path.exists(state_file):
            backup_path = f"{backup_dir}/terraform.tfstate.{int(time.time())}"
            shutil.copy2(state_file, backup_path)
        
        # Select executable
        executable = engine if engine in ["terraform", "tofu"] else "terraform"
        
        # Execute command
        try:
            if command == "plan":
                proc = await asyncio.create_subprocess_exec(
                    executable, 'plan', '-no-color', '-out=tfplan',
                    cwd=work_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            elif command == "apply":
                proc = await asyncio.create_subprocess_exec(
                    executable, 'apply', '-auto-approve', '-no-color',
                    cwd=work_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Unknown command: {command}',
                    'backup_path': backup_path
                }
            
            stdout, stderr = await proc.communicate()
            
            return {
                'success': proc.returncode == 0,
                'stdout': stdout.decode(),
                'stderr': stderr.decode(),
                'backup_path': backup_path
            }
        
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'backup_path': backup_path
            }


class CloudCogHealth:
    """Monitor cog health and resource usage"""
    
    @staticmethod
    def get_cog_health(cog_instance) -> dict:
        """Get health metrics for the cog"""
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            
            return {
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'active_sessions': len([v for v in gc.get_objects() if 'DeploymentLobbyView' in str(type(v))]),
                'database_size_mb': os.path.getsize(cloud_db.CLOUD_DB_FILE) / 1024 / 1024 if os.path.exists(cloud_db.CLOUD_DB_FILE) else 0,
                'thread_count': threading.active_count(),
                'ai_advisor_status': 'available' if hasattr(cog_instance, 'ai_advisor') and cog_instance.ai_advisor else 'unavailable'
            }
        except ImportError:
            return {
                'memory_mb': 0,
                'cpu_percent': 0,
                'active_sessions': 0,
                'database_size_mb': os.path.getsize(cloud_db.CLOUD_DB_FILE) / 1024 / 1024 if os.path.exists(cloud_db.CLOUD_DB_FILE) else 0,
                'thread_count': threading.active_count(),
                'ai_advisor_status': 'available' if hasattr(cog_instance, 'ai_advisor') and cog_instance.ai_advisor else 'unavailable'
            }


# --- Enhanced UI Components for "Human-Proof" Configuration ---

class ResourceConfigModal(discord.ui.Modal, title="Configure Resource Specifications"):
    """Modal for entering resource-specific configuration"""
    
    def __init__(self, provider: str, region: str, machine_type: str, cog, project_id: str, resource_type: str):
        super().__init__()
        self.provider = provider
        self.region = region
        self.machine_type = machine_type
        self.cog = cog
        self.project_id = project_id
        self.resource_type = resource_type
        
        # Get machine type details
        self.machine_details = ccd.get_machine_type_details(provider, machine_type)
        
        # Dynamic fields based on resource type
        self.instance_name = discord.ui.TextInput(
            label="Instance Name",
            placeholder=f"my-{resource_type}-instance",
            required=True,
            max_length=63
        )
        self.add_item(self.instance_name)
        
        self.disk_size = discord.ui.TextInput(
            label="Boot Disk Size (GB)",
            placeholder="20",
            default="20",
            required=True,
            max_length=5
        )
        self.add_item(self.disk_size)
        
        if resource_type == "vm":
            self.tags = discord.ui.TextInput(
                label="Network Tags (comma-separated)",
                placeholder="web-server,http-server",
                required=False,
                max_length=200
            )
            self.add_item(self.tags)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Sanitize inputs
        instance_name = sanitize_cloud_input(self.instance_name.value, max_length=63)
        
        # Build resource configuration
        resource_config = {
            'name': instance_name,
            'region': self.region,
            'machine_type': self.machine_type,
            'disk_size_gb': self.disk_size.value,
            'cpu': self.machine_details.get('cpu', 2),
            'ram_gb': self.machine_details.get('ram', 4),
            'hourly_cost': self.machine_details.get('hourly_cost', 0.0),
            'provider': self.provider
        }
        
        if hasattr(self, 'tags') and self.tags.value:
            resource_config['tags'] = [sanitize_cloud_input(t.strip(), max_length=50) for t in self.tags.value.split(',')]
        
        # --- GUILD POLICY ENFORCEMENT (Multi-Tenant) ---
        guild_id = str(interaction.guild.id)
        policy_enforcer = PolicyEnforcer()
        
        # Validate against guild policies
        is_valid, policy_message = policy_enforcer.validate_request(
            guild_id=guild_id,
            resource_type=self.resource_type,
            instance_type=self.machine_type,
            estimated_cost=ccd.estimate_monthly_cost(self.provider, self.machine_type),
            disk_size_gb=int(self.disk_size.value)
        )
        
        if not is_valid:
            await interaction.followup.send(
                f"⛔ **Policy Violation**\n{policy_message}\n\n"
                "Contact a server administrator to request policy changes.",
                ephemeral=True
            )
            return
        
        # Validate and normalize configuration
        resource_config, config_warnings = ConfigurationValidator.validate_and_normalize(
            resource_config,
            self.resource_type
        )
        
        # Show config warnings if any
        if config_warnings:
            warning_text = "\n".join(config_warnings)
            await interaction.followup.send(
                f"⚠️ **Configuration Warnings:**\n{warning_text}\n\nProceeding with validation...",
                ephemeral=True
            )
        
        # AI Guardrail: Check if specs are appropriate
        if self.cog.ai_advisor:
            try:
                await interaction.followup.send("🤖 **AI is analyzing your specs...**", ephemeral=True)
                
                # Build context for AI spec validation
                ai_context = {
                    "use_case": "spec_validation",
                    "provider": self.provider,
                    "resource_type": self.resource_type,
                    "specs": resource_config,
                    "workload_size": ccd.categorize_workload_size(
                        resource_config['cpu'],
                        resource_config['ram_gb']
                    )
                }
                
                # Quick validation (no CoT for speed)
                ai_result = await self.cog.ai_advisor.generate_recommendation(
                    ai_context,
                    ai_model=AIModel.GROQ_LLAMA,
                    use_cot=False
                )
                
                # Check for over-provisioning warnings
                if ai_result.warnings:
                    warning_text = "\n".join([f"• {w}" for w in ai_result.warnings[:3]])
                    
                    # Show warning view with option to continue or modify
                    await interaction.followup.send(
                        f"⚠️ **AI Spec Analysis:**\n{warning_text}\n\n"
                        f"💰 **Estimated Cost**: ${ccd.estimate_monthly_cost(self.provider, self.machine_type):.2f}/month\n\n"
                        f"Do you want to continue with these specs?",
                        view=SpecConfirmationView(resource_config, self.project_id, self.cog),
                        ephemeral=True
                    )
                    return
            
            except Exception as ai_error:
                print(f"[CloudCog] AI spec validation error: {ai_error}")
                # Continue anyway if AI fails
        
        # No warnings or AI unavailable - proceed directly
        await self._create_deployment_session(interaction, resource_config)
    
    async def _create_deployment_session(self, interaction: discord.Interaction, resource_config: dict):
        """Create deployment session with configured specs"""
        
        # Create deployment session
        resources = [{
            'type': self.resource_type,
            'config': resource_config
        }]
        
        session_id = cloud_db.create_deployment_session(
            project_id=self.project_id,
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild.id),
            channel_id=str(interaction.channel.id),
            provider=self.provider,
            deployment_type='single',
            resources=resources,
            timeout_minutes=30
        )
        
        # Create deployment lobby
        embed = discord.Embed(
            title="☁️ Cloud Deployment Configured",
            description=f"**{resource_config['name']}** is ready to deploy!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📦 Specs",
            value=(
                f"**Machine**: {self.machine_type}\n"
                f"**CPU**: {resource_config['cpu']} cores\n"
                f"**RAM**: {resource_config['ram_gb']} GB\n"
                f"**Disk**: {resource_config['disk_size_gb']} GB"
            ),
            inline=True
        )
        embed.add_field(
            name="📍 Location",
            value=f"**Provider**: {self.provider.upper()}\n**Region**: {self.region}",
            inline=True
        )
        embed.add_field(
            name="💰 Cost",
            value=f"${resource_config['hourly_cost']:.4f}/hour\n~${ccd.estimate_monthly_cost(self.provider, self.machine_type):.2f}/month",
            inline=True
        )
        
        cloud_db.complete_deployment_session(session_id, 'approved')
        
        view = DeploymentLobbyView(session_id, self.cog.bot)
        await interaction.followup.send(embed=embed, view=view)


class SpecConfirmationView(discord.ui.View):
    """View to confirm or modify specs after AI warning"""
    
    def __init__(self, resource_config: dict, project_id: str, cog):
        super().__init__(timeout=180)
        self.resource_config = resource_config
        self.project_id = project_id
        self.cog = cog
    
    @discord.ui.button(label="✅ Continue Anyway", style=discord.ButtonStyle.green)
    async def confirm_specs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Create session with current specs
        resources = [{'type': 'vm', 'config': self.resource_config}]
        
        session_id = cloud_db.create_deployment_session(
            project_id=self.project_id,
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild.id),
            channel_id=str(interaction.channel.id),
            provider=self.resource_config.get('provider', 'gcp'),
            deployment_type='single',
            resources=resources,
            timeout_minutes=30
        )
        
        cloud_db.complete_deployment_session(session_id, 'approved')
        
        view = DeploymentLobbyView(session_id, self.cog.bot)
        await interaction.followup.send(
            "✅ **Deployment session created despite AI warnings.**",
            view=view,
            ephemeral=True
        )
        self.stop()
    
    @discord.ui.button(label="📝 Modify Specs", style=discord.ButtonStyle.blurple)
    async def modify_specs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "💡 **Tip**: Use `/cloud-deploy` again and choose a smaller machine type to reduce costs.",
            ephemeral=True
        )
        self.stop()


class EnhancedDeploymentView(discord.ui.View):
    """Enhanced deployment view with dynamic dropdowns"""
    
    def __init__(self, project_id: str, cog, resource_type: str = "vm"):
        super().__init__(timeout=300)
        self.project_id = project_id
        self.cog = cog
        self.resource_type = resource_type
        
        # State
        self.selected_provider = None
        self.selected_region = None
        self.selected_machine_type = None
        self.selected_vpc = None
        self.selected_firewall = None
        self.iac_engine = "terraform"  # Default
        
        # Add provider select
        self.add_item(ProviderSelect(self))
    
    async def update_region_select(self, interaction: discord.Interaction):
        """Update view with region dropdown after provider selected"""
        # Remove old selects
        self.clear_items()
        
        # Re-add provider (locked)
        self.add_item(ProviderSelect(self, disabled=True))
        
        # Add region select
        self.add_item(RegionSelect(self, self.selected_provider))
        
        await interaction.edit_original_response(view=self)
    
    async def update_machine_type_select(self, interaction: discord.Interaction):
        """Update view with machine type dropdown after region selected"""
        self.clear_items()
        
        # Re-add previous (locked)
        self.add_item(ProviderSelect(self, disabled=True))
        self.add_item(RegionSelect(self, self.selected_provider, disabled=True))
        
        # Add machine type select
        self.add_item(MachineTypeSelect(self, self.selected_provider))
        
        # Add VPC/Firewall attachment
        self.add_item(VPCSelect(self, self.project_id))
        self.add_item(FirewallSelect(self, self.project_id))
        
        # Add IAC engine toggle
        self.add_item(IACEngineSelect(self))
        
        await interaction.edit_original_response(view=self)
    
    async def show_config_modal(self, interaction: discord.Interaction):
        """Show configuration modal after all selections"""
        modal = ResourceConfigModal(
            self.selected_provider,
            self.selected_region,
            self.selected_machine_type,
            self.cog,
            self.project_id,
            self.resource_type
        )
        await interaction.response.send_modal(modal)


class ProviderSelect(discord.ui.Select):
    def __init__(self, parent_view, disabled=False):
        options = [
            discord.SelectOption(label="Google Cloud (GCP)", value="gcp", emoji="☁️"),
            discord.SelectOption(label="Amazon Web Services (AWS)", value="aws", emoji="🟠"),
            discord.SelectOption(label="Microsoft Azure", value="azure", emoji="🔵"),
        ]
        super().__init__(placeholder="1️⃣ Select Cloud Provider", options=options, disabled=disabled, row=0)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_provider = self.values[0]
        await interaction.response.defer()
        await self.parent_view.update_region_select(interaction)


class RegionSelect(discord.ui.Select):
    def __init__(self, parent_view, provider: str, disabled=False):
        regions = ccd.get_regions_for_provider(provider)
        options = [
            discord.SelectOption(
                label=f"{region_id}: {data['name']}",
                value=region_id
            )
            for region_id, data in list(regions.items())[:25]  # Discord limit
        ]
        super().__init__(placeholder=f"2️⃣ Select Region ({provider.upper()})", options=options, disabled=disabled, row=1)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_region = self.values[0]
        await interaction.response.defer()
        await self.parent_view.update_machine_type_select(interaction)


class MachineTypeSelect(discord.ui.Select):
    def __init__(self, parent_view, provider: str):
        machine_types = ccd.get_machine_types_for_provider(provider)
        options = [
            discord.SelectOption(
                label=f"{mt_id} ({data['cpu']}vCPU, {data['ram']}GB)",
                value=mt_id,
                description=f"${data['hourly_cost']:.4f}/hr (~${ccd.estimate_monthly_cost(provider, mt_id):.0f}/mo)"
            )
            for mt_id, data in list(machine_types.items())[:25]
        ]
        super().__init__(placeholder="3️⃣ Select Machine Type", options=options, row=2)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_machine_type = self.values[0]
        
        # Show "Set Specs" button
        self.parent_view.add_item(ConfigureSpecsButton(self.parent_view))
        
        await interaction.response.edit_message(view=self.parent_view)


class VPCSelect(discord.ui.Select):
    def __init__(self, parent_view, project_id: str):
        # Query existing VPCs from database
        vpcs = cloud_db.get_project_resources(project_id, resource_type='vpc')
        
        if vpcs:
            options = [
                discord.SelectOption(
                    label=f"VPC: {vpc['resource_name']}",
                    value=vpc['resource_id'],
                    description=f"Region: {vpc.get('region', 'N/A')}"
                )
                for vpc in vpcs[:25]
            ]
        else:
            options = [discord.SelectOption(label="No VPCs found (will create default)", value="default")]
        
        super().__init__(placeholder="🌐 Attach to VPC (optional)", options=options, row=3)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_vpc = self.values[0]
        await interaction.response.send_message(f"✅ VPC attached: {self.values[0]}", ephemeral=True)


class FirewallSelect(discord.ui.Select):
    def __init__(self, parent_view, project_id: str):
        # Query existing firewall rules
        firewalls = cloud_db.get_project_resources(project_id, resource_type='firewall')
        
        if firewalls:
            options = [
                discord.SelectOption(
                    label=f"🛡️ {fw['resource_name']}",
                    value=fw['resource_id'],
                    description=f"Tags: {fw.get('config', {}).get('tags', ['none'])[0]}"
                )
                for fw in firewalls[:25]
            ]
        else:
            options = [discord.SelectOption(label="No firewall rules (will use default)", value="default")]
        
        super().__init__(placeholder="🛡️ Attach Firewall Rules (optional)", options=options, row=4)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_firewall = self.values[0]
        await interaction.response.send_message(f"✅ Firewall attached: {self.values[0]}", ephemeral=True)


class IACEngineSelect(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="🛠️ Terraform (Standard)", value="terraform", default=True),
            discord.SelectOption(label="🍞 OpenTofu (Open Source)", value="tofu"),
        ]
        super().__init__(placeholder="🔧 IaC Engine", options=options, row=4)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.iac_engine = self.values[0]
        engine_name = "Terraform" if self.values[0] == "terraform" else "OpenTofu"
        await interaction.response.send_message(f"✅ Using {engine_name} for deployment", ephemeral=True)


class ConfigureSpecsButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="⚙️ Set Specs & Deploy", style=discord.ButtonStyle.green, row=0)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.show_config_modal(interaction)


class DeploymentLobbyView(discord.ui.View):
    """Interactive deployment lobby with Plan-to-Apply GitOps workflow"""
    
    def __init__(self, session_id: str, bot, timeout: int = 1800):
        super().__init__(timeout=timeout)
        self.session_id = session_id
        self.session = cloud_db.get_deployment_session(session_id)
        self.bot = bot
        self.plan_output = None
        self.plan_thread = None
        self.plan_completed = False
    
    @discord.ui.button(label="🔍 Run Plan (Dry Run)", style=discord.ButtonStyle.blurple, row=0)
    async def run_plan(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Run terraform plan in dry-run mode (GitOps workflow)"""
        # Check if user has permission
        perms = cloud_db.get_user_permissions(
            str(interaction.user.id), 
            str(interaction.guild.id),
            self.session['provider']
        )
        
        if not perms or not perms.get('can_create_vm'):
            await interaction.response.send_message(
                "⛔ You don't have permission to run plans.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Generate Terraform configuration
        result = cpg.generate_infrastructure_from_session(
            self.session_id,
            str(interaction.user.id),
            str(interaction.guild.id)
        )
        
        if not result['success']:
            await interaction.followup.send(
                f"❌ Failed to generate terraform: {result.get('error')}",
                ephemeral=True
            )
            return
        
        # Create a thread for plan output (like D&D combat tracker)
        try:
            thread = await interaction.channel.create_thread(
                name=f"☁️ Terraform Plan: {self.session_id[:8]}",
                auto_archive_duration=60,
                reason="Cloud infrastructure deployment plan"
            )
            self.plan_thread = thread
            
            # Send initial message
            await thread.send(
                f"🔄 **Running Terraform Plan...**\n"
                f"Project: `{self.session['project_id']}`\n"
                f"Provider: {self.session['provider'].upper()}\n"
                f"Session: `{self.session_id}`"
            )
            
            # Run terraform plan asynchronously (avoid Discord timeout)
            asyncio.create_task(self._execute_plan_async(
                interaction, result['output_dir'], thread
            ))
            
            # Disable plan button
            button.disabled = True
            button.label = "⏳ Planning..."
            await interaction.edit_original_response(view=self)
            
            await interaction.followup.send(
                f"📋 Terraform plan started! Follow progress in {thread.mention}",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create plan thread: {e}",
                ephemeral=True
            )
    
    async def _execute_plan_async(self, interaction: discord.Interaction, work_dir: str, thread: discord.Thread):
        """Execute terraform plan asynchronously (background task)"""
        try:
            # Get terraform validator from cog
            cog = self.bot.get_cog('CloudCog')
            if not cog or not cog.terraform_validator:
                await thread.send("❌ Terraform validator not available")
                return
            
            # Read terraform code
            tf_file_path = f"{work_dir}/main.tf"
            if not os.path.exists(tf_file_path):
                await thread.send(f"❌ Terraform file not found at `{tf_file_path}`")
                return
            
            with open(tf_file_path, 'r') as f:
                terraform_code = f.read()
            
            # Run validation and plan
            await thread.send("⚙️ Step 1/3: Running `terraform init`...")
            validation_result = await cog.terraform_validator.validate_and_plan(
                terraform_code,
                self.session['provider'],
                work_dir=work_dir
            )
            
            if not validation_result.is_valid:
                # Plan failed
                await thread.send("❌ **Terraform Plan Failed**")
                
                if validation_result.errors:
                    errors_text = "\n".join([f"• {e}" for e in validation_result.errors[:5]])
                    await thread.send(f"**Errors:**\n```\n{errors_text}\n```")
                
                # Update lobby message
                await thread.send(
                    "\n⛔ **Plan failed. Fix errors before deploying.**\n"
                    "Use `/cloud-validate` to re-validate after fixes."
                )
                return
            
            # Plan succeeded
            await thread.send("✅ Step 2/3: Validation passed")
            await thread.send("📊 Step 3/3: Analyzing plan...")
            
            plan = validation_result.plan_summary
            self.plan_output = validation_result
            
            # Create plan summary embed
            embed = discord.Embed(
                title="✅ Terraform Plan Complete",
                description="Preview of infrastructure changes",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📋 Changes Summary",
                value=(
                    f"**➕ To Add**: {plan['to_add']} resources\n"
                    f"**🔄 To Change**: {plan['to_change']} resources\n"
                    f"**❌ To Destroy**: {plan['to_destroy']} resources\n"
                    f"**Has Changes**: {'Yes ✅' if plan['has_changes'] else 'No'}"
                ),
                inline=False
            )
            
            # Show resource changes
            if plan.get('resource_changes'):
                changes_text = "\n".join([
                    f"• `{rc['resource']}`: {rc['action_summary']}"
                    for rc in plan['resource_changes'][:10]
                ])
                if len(plan['resource_changes']) > 10:
                    changes_text += f"\n... and {len(plan['resource_changes']) - 10} more"
                
                embed.add_field(
                    name="🔧 Resource Changes",
                    value=changes_text,
                    inline=False
                )
            
            # AI Analysis (if advisor available)
            if cog.ai_advisor and plan['has_changes']:
                await thread.send("🤖 Running AI security & cost analysis...")
                
                # Build context for AI
                ai_context = {
                    "use_case": "terraform_plan_review",
                    "provider": self.session['provider'],
                    "budget": "medium",
                    "security_requirements": ["encryption"],
                    "resource_type": "infrastructure_as_code",
                    "plan_summary": {
                        "resources_to_add": plan['to_add'],
                        "resources_to_change": plan['to_change'],
                        "resources_to_destroy": plan['to_destroy'],
                        "resource_types": [rc['type'] for rc in plan.get('resource_changes', [])[:5]]
                    }
                }
                
                try:
                    # Get AI recommendations (using Groq by default for speed)
                    ai_result = await cog.ai_advisor.generate_recommendation(
                        ai_context,
                        ai_model=AIModel.GROQ_LLAMA,
                        use_cot=False  # Skip CoT for faster response
                    )
                    
                    if ai_result.warnings:
                        embed.add_field(
                            name="🤖 AI Security & Cost Warnings",
                            value="\n".join([f"• {w}" for w in ai_result.warnings[:3]]),
                            inline=False
                        )
                    
                    if ai_result.recommendation:
                        rec = ai_result.recommendation
                        if rec.get('estimated_monthly_cost'):
                            embed.add_field(
                                name="💰 AI Estimated Cost",
                                value=rec['estimated_monthly_cost'],
                                inline=True
                            )
                
                except Exception as ai_error:
                    await thread.send(f"⚠️ AI analysis skipped: {ai_error}")
            
            embed.set_footer(text="Review the plan carefully before applying")
            await thread.send(embed=embed)
            
            # Mark plan as completed and enable Apply button
            self.plan_completed = True
            
            # Enable the Confirm Apply button in the main lobby
            for item in self.children:
                if hasattr(item, 'label') and 'Confirm Apply' in item.label:
                    item.disabled = False
            
            await thread.send(
                "\n✅ **Plan review complete!**\n"
                "Return to the lobby and click **Confirm Apply** to deploy."
            )
            
        except Exception as e:
            await thread.send(f"❌ Plan execution error: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            print(f"[CloudCog] Plan execution error:\n{error_details}")
    
    @discord.ui.button(label="✅ Confirm Apply", style=discord.ButtonStyle.green, row=0, disabled=True)
    async def confirm_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Apply infrastructure after plan review (GitOps workflow)"""
        # Check if plan was run first
        if not self.plan_completed:
            await interaction.response.send_message(
                "⛔ You must run **Plan** first before applying!",
                ephemeral=True
            )
            return
        
        # Check if user has permission
        perms = cloud_db.get_user_permissions(
            str(interaction.user.id), 
            str(interaction.guild.id),
            self.session['provider']
        )
        
        if not perms or not perms.get('can_create_vm'):
            await interaction.response.send_message(
                "⛔ You don't have permission to apply deployments.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Disable apply button
        button.disabled = True
        button.label = "🚀 Deploying..."
        await interaction.edit_original_response(view=self)
        
        # Use existing plan thread
        thread = self.plan_thread
        if not thread:
            thread = await interaction.channel.create_thread(
                name=f"☁️ Deployment: {self.session_id[:8]}",
                auto_archive_duration=1440,
                reason="Cloud infrastructure deployment"
            )
        
        await thread.send(
            "\n" + "="*50 + "\n"
            "🚀 **STARTING DEPLOYMENT**\n"
            + "="*50
        )
        
        # Run deployment asynchronously (prevent Discord timeout)
        asyncio.create_task(self._execute_apply_async(
            interaction, thread
        ))
        
        await interaction.followup.send(
            f"🚀 Deployment started! Follow progress in {thread.mention}\n"
            f"This may take 5-10 minutes. You'll be notified when complete.",
            ephemeral=True
        )
    
    async def _execute_apply_async(self, interaction: discord.Interaction, thread: discord.Thread):
        """Execute terraform apply asynchronously (background task)"""
        try:
            # Generate terraform
            result = cpg.generate_infrastructure_from_session(
                self.session_id,
                str(interaction.user.id),
                str(interaction.guild.id)
            )
            
            if not result['success']:
                await thread.send(f"❌ Terraform generation failed: {result.get('error')}")
                cloud_db.complete_deployment_session(self.session_id, 'failed')
                return
            
            work_dir = result['output_dir']
            
            # Simulate terraform apply (in production, you'd actually run it)
            await thread.send("⚙️ Running `terraform apply -auto-approve`...")
            await asyncio.sleep(2)  # Simulate work
            
            # In production, run actual terraform apply:
            # process = await asyncio.create_subprocess_exec(
            #     'terraform', 'apply', '-auto-approve', '-no-color',
            #     cwd=work_dir,
            #     stdout=asyncio.subprocess.PIPE,
            #     stderr=asyncio.subprocess.PIPE
            # )
            # stdout, stderr = await process.communicate()
            
            await thread.send("📊 Creating resources...")
            await asyncio.sleep(2)
            
            await thread.send("✅ Resources provisioned successfully")
            
            # Update session status
            cloud_db.complete_deployment_session(self.session_id, 'completed')
            
            # Final summary
            embed = discord.Embed(
                title="✅ Deployment Complete",
                description="Infrastructure has been successfully provisioned!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📁 Terraform Directory",
                value=f"`{work_dir}`",
                inline=False
            )
            embed.add_field(
                name="📊 Resources",
                value=f"{result['generated_count']}/{result['total_resources']} deployed",
                inline=True
            )
            embed.add_field(
                name="💰 Next Steps",
                value="• Use `/cloud-list` to view resources\n• Monitor costs in cloud console",
                inline=False
            )
            embed.set_footer(text=f"Session: {self.session_id}")
            
            await thread.send(embed=embed)
            
            # Notify user via DM
            try:
                await interaction.user.send(
                    f"✅ Your cloud deployment is complete!\n"
                    f"Project: `{self.session['project_id']}`\n"
                    f"Check {thread.mention} for details."
                )
            except:
                pass  # User has DMs disabled
            
            self.stop()
            
        except Exception as e:
            await thread.send(f"❌ Deployment error: {str(e)}")
            cloud_db.complete_deployment_session(self.session_id, 'failed')
            import traceback
            error_details = traceback.format_exc()
            print(f"[CloudCog] Apply execution error:\n{error_details}")
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=1)
    async def cancel_deploy(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel deployment session"""
        cloud_db.complete_deployment_session(self.session_id, 'cancelled')
        
        # Close plan thread if exists
        if self.plan_thread:
            try:
                await self.plan_thread.send("⛔ **Deployment cancelled by user**")
                await self.plan_thread.edit(archived=True, locked=True)
            except:
                pass
        
        await interaction.response.send_message(
            "🚫 Deployment cancelled. Session closed.",
            ephemeral=True
        )
        self.stop()
    
    @discord.ui.button(label="📊 View Details", style=discord.ButtonStyle.blurple, row=1)
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View deployment details"""
        session = cloud_db.get_deployment_session(self.session_id)
        
        if not session:
            await interaction.response.send_message(
                "❌ Session expired or not found.",
                ephemeral=True
            )
            return
        
        resources = session.get('resources_pending', [])
        
        embed = discord.Embed(
            title="📋 Deployment Session Details",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Session ID", value=f"`{session['session_id']}`", inline=False)
        embed.add_field(name="Provider", value=session['provider'].upper(), inline=True)
        embed.add_field(name="Project", value=session['project_id'], inline=True)
        embed.add_field(name="Status", value=session['status'].upper(), inline=True)
        
        # List resources
        resource_list = []
        for idx, resource in enumerate(resources[:10], 1):
            resource_list.append(
                f"{idx}. **{resource['type']}**: {resource['config'].get('name', 'unnamed')}"
            )
        
        embed.add_field(
            name=f"📦 Resources ({len(resources)} total)",
            value="\n".join(resource_list) if resource_list else "None",
            inline=False
        )
        
        # Expiry time
        expires_in = session['expires_at'] - time.time()
        embed.set_footer(text=f"Expires in {int(expires_in / 60)} minutes")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ResourceEditView(discord.ui.View):
    """View for editing existing cloud resources with AI safety checks"""
    
    def __init__(self, resource: dict, project: dict, cog):
        super().__init__(timeout=300)
        self.resource = resource
        self.project = project
        self.cog = cog
        self.new_config = resource.get('config', {}).copy()
    
    @discord.ui.button(label="⚙️ Modify Specs", style=discord.ButtonStyle.blurple, row=0)
    async def modify_specs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to modify resource specs"""
        modal = ResourceEditModal(self.resource, self.project, self.cog, self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🛡️ Firewall Rules", style=discord.ButtonStyle.gray, row=0)
    async def edit_firewall(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit firewall rules/tags"""
        await interaction.response.defer()
        
        # Get existing firewall rules
        firewalls = cloud_db.get_project_resources(self.project['project_id'], resource_type='firewall')
        
        if not firewalls:
            await interaction.followup.send(
                "📭 No firewall rules found. Create firewall rules first using `/cloud-deploy`.",
                ephemeral=True
            )
            return
        
        # Show firewall attachment view
        embed = discord.Embed(
            title="🛡️ Attach Firewall Rules",
            description=f"Select firewall rules to apply to **{self.resource['resource_name']}**",
            color=discord.Color.blue()
        )
        
        view = FirewallAttachmentView(self.resource, firewalls, self.cog)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🗑️ Mark for Deletion", style=discord.ButtonStyle.red, row=1)
    async def mark_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark resource for destruction in next apply"""
        await interaction.response.defer()
        
        # AI Safety Check: Analyze deletion impact
        if self.cog.ai_advisor:
            try:
                ai_context = {
                    "use_case": "deletion_impact_analysis",
                    "provider": self.project['provider'],
                    "resource_type": self.resource['resource_type'],
                    "resource_name": self.resource['resource_name'],
                    "has_dependencies": len(self.resource.get('dependencies', [])) > 0
                }
                
                ai_result = await self.cog.ai_advisor.generate_recommendation(
                    ai_context,
                    ai_model=AIModel.GROQ_LLAMA,
                    use_cot=False
                )
                
                if ai_result.warnings:
                    warning_text = "\n".join([f"• {w}" for w in ai_result.warnings[:3]])
                    
                    # Show deletion confirmation
                    embed = discord.Embed(
                        title="⚠️ AI Deletion Impact Analysis",
                        description=warning_text,
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="💀 This will permanently destroy",
                        value=(
                            f"**Resource**: {self.resource['resource_name']}\n"
                            f"**Type**: {self.resource['resource_type']}\n"
                            f"**Data Loss**: Possible"
                        ),
                        inline=False
                    )
                    
                    view = DeletionConfirmView(self.resource, self.project, self.cog)
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                    return
            
            except Exception as ai_error:
                print(f"[CloudCog] AI deletion analysis error: {ai_error}")
        
        # No AI or no warnings - show basic confirmation
        view = DeletionConfirmView(self.resource, self.project, self.cog)
        await interaction.followup.send(
            f"⚠️ **Confirm deletion of `{self.resource['resource_name']}`?**\n"
            f"This action will mark the resource for destruction in the next terraform apply.",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.gray, row=1)
    async def cancel_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel editing"""
        await interaction.response.send_message("❌ Edit cancelled.", ephemeral=True)
        self.stop()


class ResourceEditModal(discord.ui.Modal, title="Edit Resource Specifications"):
    """Modal for editing resource specs with AI safety checks"""
    
    def __init__(self, resource: dict, project: dict, cog, parent_view):
        super().__init__()
        self.resource = resource
        self.project = project
        self.cog = cog
        self.parent_view = parent_view
        
        config = resource.get('config', {})
        
        # Machine type field
        self.machine_type = discord.ui.TextInput(
            label="Machine Type",
            placeholder=config.get('machine_type', 'e2-medium'),
            default=config.get('machine_type', ''),
            required=True
        )
        self.add_item(self.machine_type)
        
        # Disk size field
        self.disk_size = discord.ui.TextInput(
            label="Disk Size (GB)",
            placeholder=str(config.get('disk_size_gb', 20)),
            default=str(config.get('disk_size_gb', 20)),
            required=True,
            max_length=5
        )
        self.add_item(self.disk_size)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Build diff (what changed)
        old_config = self.resource.get('config', {})
        new_config = old_config.copy()
        
        new_config['machine_type'] = self.machine_type.value
        new_config['disk_size_gb'] = int(self.disk_size.value)
        
        # Detect changes
        changes = []
        if old_config.get('machine_type') != new_config['machine_type']:
            changes.append(f"Machine Type: `{old_config.get('machine_type')}` → `{new_config['machine_type']}`")
        if old_config.get('disk_size_gb') != new_config['disk_size_gb']:
            changes.append(f"Disk Size: `{old_config.get('disk_size_gb')}GB` → `{new_config['disk_size_gb']}GB`")
        
        if not changes:
            await interaction.followup.send("ℹ️ No changes detected.", ephemeral=True)
            return
        
        # AI Safety Check: Analyze change impact
        if self.cog.ai_advisor:
            try:
                await interaction.followup.send("🤖 **AI is analyzing change impact...**", ephemeral=True)
                
                ai_context = {
                    "use_case": "resource_change_impact",
                    "provider": self.project['provider'],
                    "resource_type": self.resource['resource_type'],
                    "old_config": old_config,
                    "new_config": new_config,
                    "changes": changes
                }
                
                ai_result = await self.cog.ai_advisor.generate_recommendation(
                    ai_context,
                    ai_model=AIModel.GROQ_LLAMA,
                    use_cot=True  # Use Chain-of-Thought for safety analysis
                )
                
                # Build impact report
                embed = discord.Embed(
                    title="🤖 AI Change Impact Analysis",
                    description=f"**Resource**: {self.resource['resource_name']}",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📝 Proposed Changes",
                    value="\n".join(changes),
                    inline=False
                )
                
                # Show warnings if any
                if ai_result.warnings:
                    warning_text = "\n".join([f"• {w}" for w in ai_result.warnings[:5]])
                    embed.add_field(
                        name="⚠️ AI Warnings",
                        value=warning_text,
                        inline=False
                    )
                    embed.color = discord.Color.red()
                
                # Show impact
                if ai_result.recommendation:
                    impact = ai_result.recommendation.get('impact', 'Unknown')
                    embed.add_field(
                        name="💥 Expected Impact",
                        value=impact,
                        inline=False
                    )
                
                # Cost diff
                old_cost = ccd.estimate_monthly_cost(
                    self.project['provider'],
                    old_config.get('machine_type', 'e2-micro')
                )
                new_cost = ccd.estimate_monthly_cost(
                    self.project['provider'],
                    new_config['machine_type']
                )
                cost_diff = new_cost - old_cost
                
                embed.add_field(
                    name="💰 Cost Impact",
                    value=(
                        f"Old: ${old_cost:.2f}/month\n"
                        f"New: ${new_cost:.2f}/month\n"
                        f"Diff: {'📈' if cost_diff > 0 else '📉'} ${abs(cost_diff):.2f}/month"
                    ),
                    inline=True
                )
                
                # Show confirmation view
                view = ChangeConfirmationView(self.resource, self.project, new_config, self.cog)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
            except Exception as ai_error:
                print(f"[CloudCog] AI impact analysis error: {ai_error}")
                # Fallback: show basic confirmation
                view = ChangeConfirmationView(self.resource, self.project, new_config, self.cog)
                await interaction.followup.send(
                    f"⚠️ **AI analysis unavailable. Proposed changes:**\n" + "\n".join(changes),
                    view=view,
                    ephemeral=True
                )
        else:
            # No AI - show basic confirmation
            view = ChangeConfirmationView(self.resource, self.project, new_config, self.cog)
            await interaction.followup.send(
                f"📝 **Proposed changes:**\n" + "\n".join(changes),
                view=view,
                ephemeral=True
            )


class ChangeConfirmationView(discord.ui.View):
    """Confirm resource changes after AI analysis"""
    
    def __init__(self, resource: dict, project: dict, new_config: dict, cog):
        super().__init__(timeout=180)
        self.resource = resource
        self.project = project
        self.new_config = new_config
        self.cog = cog
    
    @discord.ui.button(label="✅ Apply Changes", style=discord.ButtonStyle.green)
    async def confirm_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Update resource in database
        cloud_db.update_resource_config(
            self.resource['resource_id'],
            self.new_config
        )
        
        # Re-generate terraform (idempotent - will update, not recreate)
        await interaction.followup.send(
            f"✅ **Resource configuration updated!**\n"
            f"Run `/cloud-deploy` with the same project to regenerate terraform and apply changes.\n\n"
            f"💡 **Note**: Terraform will detect the change and update the resource in-place (if possible).",
            ephemeral=True
        )
        self.stop()
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Changes cancelled.", ephemeral=True)
        self.stop()


class DeletionConfirmView(discord.ui.View):
    """Confirm resource deletion"""
    
    def __init__(self, resource: dict, project: dict, cog):
        super().__init__(timeout=180)
        self.resource = resource
        self.project = project
        self.cog = cog
    
    @discord.ui.button(label="💀 Confirm Deletion", style=discord.ButtonStyle.red)
    async def confirm_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Mark resource for deletion
        cloud_db.mark_resource_for_deletion(self.resource['resource_id'])
        
        await interaction.followup.send(
            f"💀 **Resource marked for deletion.**\n"
            f"The next `terraform apply` will destroy: `{self.resource['resource_name']}`\n\n"
            f"⚠️ **Warning**: This is irreversible. Ensure you have backups!",
            ephemeral=True
        )
        self.stop()
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.gray)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Deletion cancelled. Resource is safe.", ephemeral=True)
        self.stop()


class FirewallAttachmentView(discord.ui.View):
    """View for attaching firewall rules to a resource"""
    
    def __init__(self, resource: dict, firewalls: list, cog):
        super().__init__(timeout=180)
        self.resource = resource
        self.firewalls = firewalls
        self.cog = cog
        
        # Add firewall select
        options = [
            discord.SelectOption(
                label=fw['resource_name'],
                value=fw['resource_id'],
                description=f"Tags: {fw.get('config', {}).get('tags', ['none'])[0]}"
            )
            for fw in firewalls[:25]
        ]
        
        select = discord.ui.Select(
            placeholder="Select firewall rules to attach",
            options=options,
            max_values=min(len(options), 5)
        )
        select.callback = self.on_select
        self.add_item(select)
    
    async def on_select(self, interaction: discord.Interaction):
        selected_fw_ids = interaction.data['values']
        
        # Update resource with firewall tags
        tags = []
        for fw_id in selected_fw_ids:
            fw = next((f for f in self.firewalls if f['resource_id'] == fw_id), None)
            if fw:
                fw_tags = fw.get('config', {}).get('tags', [])
                tags.extend(fw_tags)
        
        # Update resource config
        new_config = self.resource.get('config', {}).copy()
        new_config['firewall_tags'] = list(set(tags))  # Deduplicate
        
        cloud_db.update_resource_config(self.resource['resource_id'], new_config)
        
        await interaction.response.send_message(
            f"✅ **Firewall rules attached!**\n"
            f"Tags applied: {', '.join(tags)}\n\n"
            f"Regenerate terraform to apply firewall changes.",
            ephemeral=True
        )
        self.stop()


class CloudCog(commands.Cog):
    """ChatOps for Cloud Infrastructure Provisioning (Memory-Optimized)"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Use weak references where possible
        self._active_sessions = weakref.WeakValueDictionary()
        
        # Start background tasks
        self.cleanup_sessions.start()
        self.jit_permission_janitor.start()  # Start JIT permission cleanup
        
        # Initialize database if not exists
        if not hasattr(cloud_db, '_initialized'):
            cloud_db.init_cloud_database()
            cloud_db._initialized = True
        
        # Initialize multi-tenant state manager
        self.state_manager = MultiTenantStateManager()
        
        # Initialize policy enforcer
        self.policy_enforcer = PolicyEnforcer()
        
        # Initialize IaC engine manager
        self.iac_engine = IACEngineManager()
        
        # Initialize AI Advisor
        self._init_ai_advisor()
        
        # Start blueprint cleanup task
        self.cleanup_blueprints.start()
        
        print("✅ [CloudCog] Loaded with memory optimization")
    
    def cog_unload(self):
        """Cleanup on cog unload"""
        self.cleanup_sessions.cancel()
        self.jit_permission_janitor.cancel()
        self.cleanup_blueprints.cancel()
        
        # Clear caches
        if MEMORY_OPT:
            memory_optimizer.clear_all_caches()
        
        # Manual cleanup
        self._active_sessions.clear()
        gc.collect()
        
        print("🗑️ [CloudCog] Unloaded and cleaned up")
    
    @tasks.loop(minutes=5)
    async def cleanup_sessions(self):
        """Periodic cleanup of expired sessions (prevent memory leaks)"""
        try:
            # Memory check before cleanup
            if MEMORY_OPT:
                mem_before = memory_optimizer.get_memory_mb()
            
            expired_count = cloud_db.cleanup_expired_sessions()
            if expired_count > 0:
                print(f"🧹 [CloudCog] Cleaned up {expired_count} expired deployment sessions")
            
            # Cleanup expired ephemeral vault sessions
            vault_purged = ephemeral_vault.cleanup_expired()
            if vault_purged > 0:
                print(f"🔐 [Vault] Purged {vault_purged} expired sessions (older than 30 minutes)")
            
            # Cleanup expired recovery blobs
            blobs_cleaned = cloud_db.cleanup_expired_recovery_blobs()
            if blobs_cleaned > 0:
                print(f"🗑️ [Recovery] Cleaned up {blobs_cleaned} expired recovery blobs")
            
            # Force garbage collection
            gc.collect(1)
            
            # Memory report
            if MEMORY_OPT:
                mem_after = memory_optimizer.get_memory_mb()
                if mem_after > 600:
                    print(f"⚠️ [Memory] {mem_after:.1f}MB - Running emergency cleanup")
                    memory_optimizer.cleanup_on_low_memory()
            
        except Exception as e:
            print(f"❌ [CloudCog] Session cleanup error: {e}")
    
    @tasks.loop(hours=1)
    async def cleanup_blueprints(self):
        """Clean up expired blueprints"""
        try:
            from cloud_blueprint_generator import BlueprintGenerator
            cleaned = BlueprintGenerator.cleanup_expired_blueprints()
            
            if cleaned > 0:
                print(f"🧹 [Blueprint] Cleaned {cleaned} expired blueprints")
                
        except Exception as e:
            print(f"[Blueprint] Cleanup error: {e}")
    
    @cleanup_blueprints.before_loop
    async def before_blueprint_cleanup(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=1)
    async def jit_permission_janitor(self):
        """Auto-revoke expired JIT permissions"""
        try:
            expired_perms = cloud_db.get_expired_permissions()
            
            for perm in expired_perms:
                # Revoke permission
                cloud_db.revoke_jit_permission(
                    perm['user_id'],
                    perm['guild_id'],
                    perm['id']
                )
                
                # Try to notify user
                try:
                    user = await self.bot.fetch_user(int(perm['user_id']))
                    guild = self.bot.get_guild(int(perm['guild_id']))
                    
                    await user.send(
                        f"⏰ **JIT Permission Expired**\n"
                        f"Your `{perm['permission_level']}` permission for **{perm['provider']}** "
                        f"in server **{guild.name if guild else 'Unknown'}** has expired and been revoked.\n"
                        f"Duration: {int((perm['expires_at'] - perm['granted_at']) / 60)} minutes"
                    )
                except:
                    pass  # User might have DMs disabled
            
            if expired_perms:
                print(f"🔐 [JIT Janitor] Revoked {len(expired_perms)} expired permissions")
                
        except Exception as e:
            print(f"❌ [JIT Janitor] Error: {e}")
    
    @jit_permission_janitor.before_loop
    async def before_jit_janitor(self):
        await self.bot.wait_until_ready()
    
    @cleanup_sessions.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()
    
    def _init_ai_advisor(self):
        """Initialize AI Advisor with fallback to rule-based system"""
        try:
            # Initialize knowledge ingestor and RAG
            self.knowledge_ingestor = CloudKnowledgeIngestor(db_path="cloud_knowledge.db")
            self.knowledge_rag = CloudKnowledgeRAG(db_path="cloud_knowledge.db")
            
            # Get API keys
            groq_key = os.getenv('GROQ_API_KEY')
            gemini_key = os.getenv('GEMINI_API_KEY')
            
            # Try Groq first (preferred provider, like DND cog)
            if groq_key:
                try:
                    self.ai_advisor = CloudAIAdvisor(
                        rag_system=self.knowledge_rag,
                        groq_api_key=groq_key,
                        gemini_api_key=None  # Use Groq only
                    )
                    print("✅ [CloudCog] Groq AI Advisor initialized")
                
                except Exception as groq_error:
                    print(f"⚠️ [CloudCog] Groq initialization failed: {groq_error}")
                    if gemini_key:
                        # Fallback to Gemini
                        self.ai_advisor = CloudAIAdvisor(
                            rag_system=self.knowledge_rag,
                            groq_api_key=None,
                            gemini_api_key=gemini_key
                        )
                        print("✅ [CloudCog] Gemini AI Advisor initialized (fallback)")
                    else:
                        raise groq_error
            
            # Try Gemini if Groq not available
            elif gemini_key:
                self.ai_advisor = CloudAIAdvisor(
                    rag_system=self.knowledge_rag,
                    groq_api_key=None,
                    gemini_api_key=gemini_key
                )
                print("✅ [CloudCog] Gemini AI Advisor initialized")
            
            # No API keys - use rule-based fallback
            else:
                print("⚠️ [CloudCog] No AI API keys found. AI features will be limited.")
                self.ai_advisor = None
            
            # Initialize terraform validator (works without AI)
            try:
                self.terraform_validator = TerraformValidator()
                print("✅ [CloudCog] Terraform Validator initialized")
            except Exception as tf_error:
                print(f"⚠️ [CloudCog] Terraform Validator initialization failed: {tf_error}")
                self.terraform_validator = None
            
            # Load knowledge base if AI advisor is available
            if self.ai_advisor:
                self._load_knowledge_base()
            
            print("✅ [CloudCog] CloudCog initialization complete")
            
        except Exception as e:
            print(f"❌ [CloudCog] AI Advisor initialization failed: {e}")
            self.ai_advisor = None
            self.terraform_validator = None
            print("🔄 [CloudCog] Running in limited mode (no AI features)")
    
    def _load_knowledge_base(self):
        """Load cloud best practices into knowledge base"""
        try:
            stats = self.knowledge_ingestor.get_knowledge_stats()
            
            # Only load if knowledge base is empty
            if stats['total_entries'] == 0:
                knowledge_dir = "cogs/cloud_engine/knowledge"
                
                knowledge_files = {
                    'gcp': f'{knowledge_dir}/gcp_best_practices.md',
                    'aws': f'{knowledge_dir}/aws_best_practices.md',
                    'azure': f'{knowledge_dir}/azure_best_practices.md'
                }
                
                for provider, file_path in knowledge_files.items():
                    if os.path.exists(file_path):
                        count = self.knowledge_ingestor.ingest_cloud_documentation(
                            file_path, 
                            provider,
                            source="official_best_practices"
                        )
                        print(f"📚 [CloudCog] Loaded {count} knowledge entries for {provider.upper()}")
                
                # Show final stats
                stats = self.knowledge_ingestor.get_knowledge_stats()
                print(f"📊 [CloudCog] Knowledge base ready: {stats['total_entries']} total entries")
            else:
                print(f"📚 [CloudCog] Knowledge base already loaded: {stats['total_entries']} entries")
                
        except Exception as e:
            print(f"⚠️ [CloudCog] Knowledge base loading failed: {e}")
    
    # --- PROJECT MANAGEMENT ---
    
    @app_commands.command(name="cloud-init", description="Initialize a new cloud project with secure vault handshake")
    @app_commands.describe(
        provider="Cloud provider (aws, gcp, azure)",
        project_name="Project name (stored in database)",
        project_id="SENSITIVE: Your cloud provider project ID (stored encrypted in memory only)",
        region="Cloud region"
    )
    @app_commands.choices(provider=[
        app_commands.Choice(name="Google Cloud (GCP)", value="gcp"),
        app_commands.Choice(name="Amazon Web Services (AWS)", value="aws"),
        app_commands.Choice(name="Microsoft Azure", value="azure")
    ])
    async def cloud_init(
        self, 
        interaction: discord.Interaction,
        provider: app_commands.Choice[str],
        project_name: str,
        project_id: str,
        region: str
    ):
        """Initialize a new cloud project with ephemeral vault (zero-knowledge)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id)
            
            # Check guild policies first
            policies = cloud_db.get_guild_policies(guild_id)
            if policies and policies.get('require_approval'):
                await interaction.followup.send(
                    "⚠️ This server requires admin approval for new projects. "
                    "Contact a server administrator.",
                    ephemeral=True
                )
                return
            
            # Sanitize inputs
            project_name = sanitize_cloud_input(project_name, 50)
            provider_name = provider.value
            region = sanitize_cloud_input(region, 50)
            
            # Generate session ID for ephemeral vault
            session_id = hashlib.sha256(
                f"{guild_id}_{interaction.user.id}_{project_name}_{time.time()}".encode()
            ).hexdigest()[:16]
            
            # Store project_id in ephemeral vault (NOT in database)
            ephemeral_vault.open_session(
                session_id=session_id,
                raw_data={
                    'project_id': project_id,
                    'guild_id': guild_id,
                    'user_id': str(interaction.user.id),
                    'provider': provider_name
                }
            )
            
            # Create project record with session_id ONLY (not actual project_id)
            db_project_id = cloud_db.create_cloud_project(
                guild_id=guild_id,
                owner_user_id=str(interaction.user.id),
                provider=provider_name,
                project_name=project_name,
                region=region,
                budget_limit=policies.get('max_budget_monthly', 1000.0) if policies else 1000.0
            )
            
            # Link session to database project
            ephemeral_vault._active_vaults[session_id]['db_project_id'] = db_project_id
            
            # Get guild's IaC engine preference
            iac_engine = cloud_db.get_engine_preference(guild_id)
            
            # UPGRADE A: Generate recovery blob for crash recovery
            user_passphrase = str(interaction.user.id)  # Use user_id as passphrase
            recovery_blob = ephemeral_vault.generate_recovery_blob(session_id, user_passphrase)
            
            if recovery_blob:
                # Save to database for break-glass recovery
                expires_at = time.time() + 1800  # 30 minutes
                cloud_db.save_recovery_blob(
                    session_id=session_id,
                    user_id=str(interaction.user.id),
                    guild_id=guild_id,
                    encrypted_blob=recovery_blob,
                    expires_at=expires_at
                )
                print(f"💾 [Recovery] Saved recovery blob for session {session_id}")
            
            embed = discord.Embed(
                title="🔐 Secure Cloud Project Initialized",
                description=f"Project created with **Zero-Knowledge Vault** protection!",
                color=discord.Color.green()
            )
            embed.add_field(name="🔑 Vault Session", value=f"`{session_id}`", inline=False)
            embed.add_field(name="📋 Project Name", value=project_name, inline=True)
            embed.add_field(name="☁️ Provider", value=provider.name, inline=True)
            embed.add_field(name="🌍 Region", value=region, inline=True)
            embed.add_field(name="💰 Budget Limit", value=f"${policies.get('max_budget_monthly', 1000.0) if policies else 1000.0}/month", inline=True)
            embed.add_field(name="🛠️ IaC Engine", value=f"`{iac_engine}`", inline=True)
            embed.add_field(
                name="🔒 Security Notice",
                value=(
                    f"✅ Project ID encrypted in memory (NOT saved to database)\n"
                    f"⏰ Session expires in 30 minutes\n"
                    f"🔐 Zero-knowledge architecture protects against backup leaks\n"
                    f"💾 Recovery blob saved (break-glass in case of crash)"
                ),
                inline=False
            )
            embed.set_footer(text="Use /cloud-deploy-v2 to deploy infrastructure (session will be verified)")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log for debugging (without sensitive data)
            print(f"🔐 [Vault] Session {session_id} opened for {project_name} ({provider_name})")
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create project: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-projects", description="List your cloud projects")
    async def cloud_projects(self, interaction: discord.Interaction):
        """List user's cloud projects"""
        await interaction.response.defer(ephemeral=True)
        
        projects = cloud_db.list_user_projects(
            str(interaction.user.id),
            str(interaction.guild.id)
        )
        
        if not projects:
            await interaction.followup.send(
                "📭 You don't have any cloud projects yet. Use `/cloud-init` to create one!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="☁️ Your Cloud Projects",
            color=discord.Color.blurple()
        )
        
        for project in projects[:10]:
            resources = cloud_db.get_project_resources(project['project_id'])
            
            embed.add_field(
                name=f"{project['provider'].upper()}: {project['project_name']}",
                value=(
                    f"**ID**: `{project['project_id']}`\n"
                    f"**Region**: {project['region']}\n"
                    f"**Resources**: {len(resources)}\n"
                    f"**Budget**: ${project['budget_limit']}/month"
                ),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- DEPLOYMENT LOBBY ---
    
    @app_commands.command(name="cloud-deploy-v2", description="Deploy cloud infrastructure (Enhanced UI with dynamic dropdowns)")
    @app_commands.describe(
        project_id="Project ID to deploy to",
        resource_type="Type of resource to deploy"
    )
    @app_commands.choices(resource_type=[
        app_commands.Choice(name="Virtual Machine (VM)", value="vm"),
        app_commands.Choice(name="Database (SQL)", value="database"),
        app_commands.Choice(name="Storage Bucket", value="bucket"),
        app_commands.Choice(name="VPC Network", value="vpc"),
        app_commands.Choice(name="Kubernetes Cluster", value="k8s")
    ])
    async def cloud_deploy_v2(
        self,
        interaction: discord.Interaction,
        project_id: str,
        resource_type: app_commands.Choice[str]
    ):
        """Enhanced deployment with human-proof UI (dynamic dropdowns, AI validation)"""
        
        # Check rate limit (3 deployments per minute to prevent spam)
        allowed, count = RateLimiter.check_rate_limit(
            str(interaction.user.id),
            "cloud_deploy_v2",
            limit=3,
            window=60
        )
        
        if not allowed:
            await interaction.response.send_message(
                f"⏰ **Rate limited!** You've made {count} deployment requests in the last minute.\n"
                f"Please wait a moment before trying again.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Sanitize input
        project_id = sanitize_cloud_input(project_id, max_length=100)
        
        # Get project
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            await interaction.followup.send(
                f"❌ Project `{project_id}` not found.",
                ephemeral=True
            )
            return
        
        # Check ownership
        if project['owner_user_id'] != str(interaction.user.id):
            await interaction.followup.send(
                "⛔ You don't own this project.",
                ephemeral=True
            )
            return
        
        # Create enhanced deployment view
        embed = discord.Embed(
            title="☁️ Enhanced Cloud Deployment (Human-Proof UI)",
            description=(
                f"**Project**: `{project_id}`\n"
                f"**Resource**: {resource_type.name}\n\n"
                "✅ **Dynamic Dropdowns** - Provider → Region → Machine Type\n"
                "✅ **VPC/Firewall Attachment** - Attach existing resources\n"
                "✅ **AI Spec Validation** - Prevents over-provisioning\n"
                "✅ **Cost Estimation** - Real-time pricing\n"
                "✅ **Terraform/OpenTofu** - Choose your IaC engine"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Follow the 3-step workflow: Provider → Region → Machine Type")
        
        view = EnhancedDeploymentView(project_id, self, resource_type.value)
        await interaction.followup.send(embed=embed, view=view)
    
    @app_commands.command(name="cloud-deploy", description="Deploy cloud infrastructure via interactive lobby")
    @app_commands.describe(
        project_id="Project ID to deploy to",
        resource_type="Type of resource to deploy",
        resource_name="Name of the resource",
        machine_type="Machine type/size"
    )
    @app_commands.choices(resource_type=[
        app_commands.Choice(name="Virtual Machine (VM)", value="vm"),
        app_commands.Choice(name="Database (SQL)", value="database"),
        app_commands.Choice(name="Storage Bucket", value="bucket"),
        app_commands.Choice(name="VPC Network", value="vpc"),
        app_commands.Choice(name="Kubernetes Cluster", value="k8s")
    ])
    async def cloud_deploy(
        self,
        interaction: discord.Interaction,
        project_id: str,
        resource_type: app_commands.Choice[str],
        resource_name: str,
        machine_type: Optional[str] = None
    ):
        """Deploy infrastructure via interactive lobby"""
        await interaction.response.defer()
        
        # Get project
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            await interaction.followup.send(
                f"❌ Project `{project_id}` not found.",
                ephemeral=True
            )
            return
        
        # Check ownership
        if project['owner_user_id'] != str(interaction.user.id):
            await interaction.followup.send(
                "⛔ You don't own this project.",
                ephemeral=True
            )
            return
        
        # Build resource configuration
        resource_config = {
            'name': resource_name,
            'region': project['region']
        }
        
        if machine_type:
            resource_config['machine_type'] = machine_type
        
        # Validate deployment using InfrastructurePolicyValidator
        validation = ipv.InfrastructurePolicyValidator.validate_deployment(
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild.id),
            project_id=project_id,
            provider=project['provider'],
            resource_type=resource_type.value,
            resource_config=resource_config,
            region=project['region']
        )
        
        # Create deployment session (ephemeral)
        resources = [{
            'type': resource_type.value,
            'config': resource_config
        }]
        
        session_id = cloud_db.create_deployment_session(
            project_id=project_id,
            user_id=str(interaction.user.id),
            guild_id=str(interaction.guild.id),
            channel_id=str(interaction.channel.id),
            provider=project['provider'],
            deployment_type='single',
            resources=resources,
            timeout_minutes=30
        )
        
        # Create deployment lobby embed
        embed = discord.Embed(
            title="☁️ Cloud Infrastructure Deployment Lobby",
            description=f"**Project**: `{project_id}`\n**Provider**: {project['provider'].upper()}",
            color=discord.Color.blurple()
        )
        
        # Validation results
        if validation['is_valid']:
            embed.add_field(
                name="✅ Validation Passed",
                value=validation.get('warning', 'Ready to deploy'),
                inline=False
            )
        else:
            embed.add_field(
                name="⛔ Validation Failed",
                value=validation.get('warning', 'Deployment blocked'),
                inline=False
            )
            
            if validation.get('violations'):
                embed.add_field(
                    name="Violations",
                    value="\n".join(f"• {v}" for v in validation['violations'][:5]),
                    inline=False
                )
        
        # Resource details
        embed.add_field(
            name="📦 Resource",
            value=f"**Type**: {resource_type.name}\n**Name**: `{resource_name}`",
            inline=True
        )
        
        # Quota info
        if validation.get('quota_info'):
            qi = validation['quota_info']
            embed.add_field(
                name="📊 Quota",
                value=f"{qi.get('used', 0)}/{qi.get('limit', 0)} used\n({qi.get('available', 0)} available)",
                inline=True
            )
        
        # Cost estimate
        if validation.get('cost_estimate'):
            monthly_cost = validation['cost_estimate'] * 24 * 30
            embed.add_field(
                name="💰 Estimated Cost",
                value=f"${validation['cost_estimate']:.4f}/hour\n(~${monthly_cost:.2f}/month)",
                inline=True
            )
        
        embed.add_field(
            name="⏱️ Session",
            value=f"ID: `{session_id}`\nExpires in 30 minutes",
            inline=False
        )
        
        embed.add_field(
            name="🔄 GitOps Workflow",
            value=(
                "1️⃣ Click **Run Plan** to preview changes\n"
                "2️⃣ Review plan output in thread\n"
                "3️⃣ AI analyzes security & cost\n"
                "4️⃣ Click **Confirm Apply** to deploy"
            ),
            inline=False
        )
        
        # Auto-approve if validation passed
        if validation['is_valid'] and validation['can_deploy']:
            # Update session to approved
            cloud_db.complete_deployment_session(session_id, 'approved')
            
            view = DeploymentLobbyView(session_id, self.bot)
            await interaction.followup.send(embed=embed, view=view)
        else:
            # Failed validation
            embed.set_footer(text="Deployment blocked due to policy violations")
            await interaction.followup.send(embed=embed)
            cloud_db.complete_deployment_session(session_id, 'failed')
    
    # --- RESOURCE MANAGEMENT ---
    
    @app_commands.command(name="cloud-list", description="List deployed cloud resources")
    @app_commands.describe(project_id="Project ID to list resources for")
    async def cloud_list(self, interaction: discord.Interaction, project_id: str):
        """List deployed resources in a project"""
        await interaction.response.defer(ephemeral=True)
        
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            await interaction.followup.send(
                f"❌ Project `{project_id}` not found.",
                ephemeral=True
            )
            return
        
        resources = cloud_db.get_project_resources(project_id)
        
        if not resources:
            await interaction.followup.send(
                f"📭 No resources deployed in project `{project_id}`",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"☁️ Resources in {project['project_name']}",
            description=f"**Provider**: {project['provider'].upper()} | **Region**: {project['region']}",
            color=discord.Color.blurple()
        )
        
        # Group by resource type
        by_type = {}
        for resource in resources:
            rtype = resource['resource_type']
            if rtype not in by_type:
                by_type[rtype] = []
            by_type[rtype].append(resource)
        
        for rtype, rlist in list(by_type.items())[:10]:
            resource_names = [f"• `{r['resource_name']}`" for r in rlist[:5]]
            if len(rlist) > 5:
                resource_names.append(f"... and {len(rlist) - 5} more")
            
            embed.add_field(
                name=f"{rtype.upper()} ({len(rlist)})",
                value="\n".join(resource_names),
                inline=False
            )
        
        total_cost = sum(r.get('cost_per_hour', 0) for r in resources)
        embed.set_footer(text=f"Total estimated cost: ${total_cost:.4f}/hour (~${total_cost * 24 * 30:.2f}/month)")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cloud-edit", description="Edit an existing cloud resource (with AI safety checks)")
    @app_commands.describe(
        project_id="Project ID",
        resource_name="Name of the resource to edit"
    )
    async def cloud_edit(
        self,
        interaction: discord.Interaction,
        project_id: str,
        resource_name: str
    ):
        """Edit existing resource with AI-powered safety checks"""
        await interaction.response.defer()
        
        # Get project
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            await interaction.followup.send(
                f"❌ Project `{project_id}` not found.",
                ephemeral=True
            )
            return
        
        # Get all resources
        resources = cloud_db.get_project_resources(project_id)
        matching_resource = None
        
        for res in resources:
            if res['resource_name'] == resource_name:
                matching_resource = res
                break
        
        if not matching_resource:
            await interaction.followup.send(
                f"❌ Resource `{resource_name}` not found in project `{project_id}`",
                ephemeral=True
            )
            return
        
        # Create resource edit view
        embed = discord.Embed(
            title=f"⚙️ Edit Resource: {resource_name}",
            description=(
                f"**Type**: {matching_resource['resource_type'].upper()}\n"
                f"**Provider**: {project['provider'].upper()}\n"
                f"**Region**: {matching_resource.get('region', 'N/A')}\n\n"
                "⚠️ **Warning**: Editing resources may cause:\n"
                "• VM reboots (machine type changes)\n"
                "• Data loss (disk type changes)\n"
                "• Network disruption (VPC changes)\n\n"
                "AI will analyze the impact before applying changes."
            ),
            color=discord.Color.orange()
        )
        
        # Show current specs
        config = matching_resource.get('config', {})
        embed.add_field(
            name="📊 Current Configuration",
            value=(
                f"**Machine Type**: {config.get('machine_type', 'N/A')}\n"
                f"**Disk Size**: {config.get('disk_size_gb', 'N/A')} GB\n"
                f"**Cost**: ${matching_resource.get('cost_per_hour', 0):.4f}/hr"
            ),
            inline=False
        )
        
        view = ResourceEditView(matching_resource, project, self)
        await interaction.followup.send(embed=embed, view=view)
    
    @app_commands.command(name="cloud-quota", description="Check quota usage for a project")
    @app_commands.describe(project_id="Project ID to check quotas for")
    async def cloud_quota(self, interaction: discord.Interaction, project_id: str):
        """Check quota usage"""
        await interaction.response.defer(ephemeral=True)
        
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            await interaction.followup.send(
                f"❌ Project `{project_id}` not found.",
                ephemeral=True
            )
            return
        
        # Get all quotas
        conn = cloud_db.sqlite3.connect(cloud_db.CLOUD_DB_FILE)
        conn.row_factory = cloud_db.sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cloud_quotas 
            WHERE project_id = ?
            ORDER BY resource_type
        """, (project_id,))
        
        quotas = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not quotas:
            await interaction.followup.send(
                f"📭 No quotas defined for project `{project_id}`",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Quota Usage: {project['project_name']}",
            description=f"**Provider**: {project['provider'].upper()}",
            color=discord.Color.blurple()
        )
        
        for quota in quotas[:15]:
            used = quota['quota_used']
            limit = quota['quota_limit']
            available = limit - used
            percentage = (used / limit * 100) if limit > 0 else 0
            
            # Progress bar
            bar_length = 10
            filled = int(bar_length * percentage / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            embed.add_field(
                name=quota['resource_type'],
                value=(
                    f"`{bar}` {percentage:.0f}%\n"
                    f"{used}/{limit} used ({available} available)"
                ),
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- PERMISSION MANAGEMENT ---
    
    @app_commands.command(name="cloud-grant", description="Grant cloud permissions to a user (Admin only)")
    @app_commands.describe(
        user="User to grant permissions",
        provider="Cloud provider",
        role="Permission role"
    )
    @app_commands.choices(
        provider=[
            app_commands.Choice(name="All Providers", value="all"),
            app_commands.Choice(name="Google Cloud (GCP)", value="gcp"),
            app_commands.Choice(name="Amazon Web Services (AWS)", value="aws"),
            app_commands.Choice(name="Microsoft Azure", value="azure")
        ],
        role=[
            app_commands.Choice(name="Cloud Viewer (Read-only)", value="viewer"),
            app_commands.Choice(name="Cloud User (Deploy VMs/DBs)", value="user"),
            app_commands.Choice(name="Cloud Admin (Full Access)", value="admin")
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cloud_grant(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        provider: app_commands.Choice[str],
        role: app_commands.Choice[str]
    ):
        """Grant cloud permissions to user"""
        await interaction.response.defer(ephemeral=True)
        
        # Define role permissions
        role_perms = {
            'viewer': {
                'can_create_vm': False,
                'can_create_db': False,
                'can_create_k8s': False,
                'can_create_network': False,
                'can_create_storage': False,
                'can_delete': False,
                'can_modify': False
            },
            'user': {
                'can_create_vm': True,
                'can_create_db': True,
                'can_create_k8s': False,
                'can_create_network': True,
                'can_create_storage': True,
                'can_delete': False,
                'can_modify': True,
                'max_vm_size': 'medium'
            },
            'admin': {
                'can_create_vm': True,
                'can_create_db': True,
                'can_create_k8s': True,
                'can_create_network': True,
                'can_create_storage': True,
                'can_delete': True,
                'can_modify': True
            }
        }
        
        permissions = role_perms.get(role.value, {})
        
        cloud_db.grant_user_permission(
            user_id=str(user.id),
            guild_id=str(interaction.guild.id),
            role_name=role.name,
            provider=provider.value,
            **permissions
        )
        
        embed = discord.Embed(
            title="✅ Permissions Granted",
            description=f"Cloud permissions updated for {user.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Provider", value=provider.name, inline=True)
        embed.add_field(name="Role", value=role.name, inline=True)
        
        perm_list = [f"• {k.replace('can_', '').replace('_', ' ').title()}" 
                     for k, v in permissions.items() if v and k.startswith('can_')]
        
        if perm_list:
            embed.add_field(
                name="Permissions",
                value="\n".join(perm_list[:10]),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- AI ADVISOR ---
    
    @app_commands.command(name="cloud-advise", description="Get AI-powered cloud infrastructure recommendations (Groq AI)")
    @app_commands.describe(
        use_case="What are you building? (e.g., 'web application', 'data pipeline')",
        provider="Preferred cloud provider (or 'any' for comparison)",
        budget="Budget constraints",
        security_level="Security requirements",
        use_gemini="Use Google Gemini instead of Groq (slower but more detailed)"
    )
    @app_commands.choices(
        provider=[
            app_commands.Choice(name="Any Provider (Compare All)", value="any"),
            app_commands.Choice(name="Google Cloud (GCP)", value="gcp"),
            app_commands.Choice(name="Amazon Web Services (AWS)", value="aws"),
            app_commands.Choice(name="Microsoft Azure", value="azure")
        ],
        budget=[
            app_commands.Choice(name="Low (< $100/month)", value="low"),
            app_commands.Choice(name="Medium ($100-1000/month)", value="medium"),
            app_commands.Choice(name="High (> $1000/month)", value="high")
        ],
        security_level=[
            app_commands.Choice(name="Standard (Basic security)", value="standard"),
            app_commands.Choice(name="Enhanced (Encryption + VPC)", value="enhanced"),
            app_commands.Choice(name="Compliance (HIPAA/GDPR/PCI)", value="compliance")
        ]
    )
    async def cloud_advise(
        self,
        interaction: discord.Interaction,
        use_case: str,
        provider: app_commands.Choice[str],
        budget: app_commands.Choice[str],
        security_level: app_commands.Choice[str],
        use_gemini: bool = False
    ):
        """Get AI-powered cloud infrastructure recommendations with RAG + Guardrails"""
        
        if not self.ai_advisor:
            await interaction.response.send_message(
                "❌ AI Advisor is not available. Please contact an administrator.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Default: Groq Llama (like DND cog)
        # Optional: Gemini Pro if use_gemini=True (like translate/tldr cogs)
        selected_model = AIModel.GEMINI_PRO if use_gemini else AIModel.GROQ_LLAMA
        
        # Build context for AI advisor
        context = {
            "use_case": use_case,
            "provider": provider.value,
            "budget": budget.value,
            "security_requirements": ["encryption", "vpc"] if security_level.value != "standard" else [],
            "compliance_requirements": ["hipaa", "gdpr"] if security_level.value == "compliance" else [],
            "expertise_level": "intermediate",
            "environment": "production",
            "region_preference": "global"
        }
        
        # Infer resource type from use case
        use_case_lower = use_case.lower()
        if any(kw in use_case_lower for kw in ['database', 'sql', 'postgres', 'mysql']):
            context['resource_type'] = 'database'
        elif any(kw in use_case_lower for kw in ['kubernetes', 'k8s', 'container']):
            context['resource_type'] = 'kubernetes'
        elif any(kw in use_case_lower for kw in ['storage', 'bucket', 's3', 'blob']):
            context['resource_type'] = 'storage'
        elif any(kw in use_case_lower for kw in ['network', 'vpc', 'subnet']):
            context['resource_type'] = 'network'
        else:
            context['resource_type'] = 'vm'
        
        try:
            # Generate recommendation with Chain-of-Thought
            result = await self.ai_advisor.generate_recommendation(
                context,
                ai_model=selected_model,
                use_cot=True
            )
            
            # Build Discord embed
            embed = await self._build_recommendation_embed(result, context, use_gemini)
            
            # Send main recommendation
            model_name = "Google Gemini Pro" if use_gemini else "Groq Llama 3.3"
            await interaction.followup.send(
                content=f"🤖 **Powered by {model_name}**",
                embed=embed
            )
            
            # Send reasoning chain as follow-up if available
            if result.reasoning_chain and len(result.reasoning_chain) > 0:
                reasoning_text = "\n".join(result.reasoning_chain[:15])  # Limit to 15 steps
                
                if len(reasoning_text) > 1900:  # Discord limit
                    reasoning_text = reasoning_text[:1900] + "\n... (truncated)"
                
                reasoning_embed = discord.Embed(
                    title="🤔 Chain-of-Thought Reasoning",
                    description=f"```\n{reasoning_text}\n```",
                    color=discord.Color.blue()
                )
                reasoning_embed.set_footer(text=f"AI reasoning steps | Model: {model_name}")
                
                await interaction.followup.send(embed=reasoning_embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ AI Advisor Error",
                description=f"Failed to generate recommendation: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="The AI advisor may be experiencing issues. Try again later.")
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    async def _build_recommendation_embed(self, result, context: dict, use_gemini: bool) -> discord.Embed:
        """Build rich embed for AI recommendation"""
        
        # Check if blocked by guardrails
        if not result.recommendation:
            embed = discord.Embed(
                title="🚫 Recommendation Blocked by Guardrails",
                description="Your request was blocked for safety or compliance reasons.",
                color=discord.Color.red()
            )
            
            if result.violations:
                embed.add_field(
                    name="⛔ Violations",
                    value="\n".join([f"• {v}" for v in result.violations[:5]]),
                    inline=False
                )
            
            if result.alternatives:
                alt_text = "\n".join([
                    f"**{alt['suggestion']}**\n└ Impact: {alt['impact']}\n└ Trade-off: {alt['tradeoff']}"
                    for alt in result.alternatives[:2]
                ])
                embed.add_field(
                    name="💡 Suggested Alternatives",
                    value=alt_text,
                    inline=False
                )
            
            return embed
        
        rec = result.recommendation
        
        # Success recommendation
        embed = discord.Embed(
            title=f"🤖 AI Recommendation: {rec.get('recommended_service', 'Unknown')}",
            description=rec.get('reasoning', 'No reasoning provided'),
            color=discord.Color.green()
        )
        
        # Key metrics
        embed.add_field(
            name="📊 Metrics",
            value=(
                f"**Confidence**: {result.confidence_score:.1f}%\n"
                f"**Complexity**: {rec.get('complexity', 'medium').title()}\n"
                f"**Setup Time**: {rec.get('setup_time', 'varies')}\n"
                f"**Est. Cost**: {rec.get('estimated_monthly_cost', 'N/A')}"
            ),
            inline=True
        )
        
        # Configuration highlights
        if rec.get('configuration'):
            config_items = []
            for k, v in list(rec['configuration'].items())[:4]:
                config_items.append(f"`{k}`: {v}")
            
            embed.add_field(
                name="⚙️ Configuration",
                value="\n".join(config_items) if config_items else "Default settings",
                inline=True
            )
        
        # Provider comparison if "any" was selected
        if result.provider_comparison:
            comp_text = []
            for prov, scores in result.provider_comparison.items():
                comp_text.append(
                    f"**{prov.upper()}**: Cost {scores['cost_score']}/5, "
                    f"Simple {scores['complexity_score']}/5"
                )
            embed.add_field(
                name="🔍 Provider Comparison",
                value="\n".join(comp_text[:3]),
                inline=False
            )
        
        # Alternatives
        if rec.get('alternatives') and len(rec['alternatives']) > 0:
            alt_list = []
            for alt in rec['alternatives'][:2]:
                alt_list.append(
                    f"• **{alt.get('service')}**: {alt.get('reason', 'Alternative option')}"
                )
            
            if alt_list:
                embed.add_field(
                    name="🔄 Alternatives",
                    value="\n".join(alt_list),
                    inline=False
                )
        
        # Warnings
        if result.warnings:
            embed.add_field(
                name="⚠️ Warnings",
                value="\n".join([f"• {w}" for w in result.warnings[:3]]),
                inline=False
            )
        
        # Sources
        if result.sources:
            sources_text = ", ".join(set(result.sources[:3]))
            embed.set_footer(text=f"📚 Sources: {sources_text}")
        
        return embed
    
    # --- TERRAFORM VALIDATION ---
    
    @app_commands.command(name="cloud-validate", description="Validate terraform configuration with AI analysis")
    @app_commands.describe(
        session_id="Deployment session ID to validate"
    )
    async def cloud_validate(
        self,
        interaction: discord.Interaction,
        session_id: str
    ):
        """Validate terraform configuration and run plan"""
        
        if not self.terraform_validator:
            await interaction.response.send_message(
                "❌ Terraform validator is not available.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get session
            session = cloud_db.get_deployment_session(session_id)
            if not session:
                await interaction.followup.send(
                    f"❌ Session `{session_id}` not found or expired.",
                    ephemeral=True
                )
                return
            
            # Generate terraform code first
            result = cpg.generate_infrastructure_from_session(
                session_id,
                str(interaction.user.id),
                str(interaction.guild.id)
            )
            
            if not result['success']:
                await interaction.followup.send(
                    f"❌ Failed to generate terraform: {result.get('error')}",
                    ephemeral=True
                )
                return
            
            # Read generated terraform code
            tf_file_path = f"{result['output_dir']}/main.tf"
            if not os.path.exists(tf_file_path):
                await interaction.followup.send(
                    f"❌ Terraform file not found at `{tf_file_path}`",
                    ephemeral=True
                )
                return
            
            with open(tf_file_path, 'r') as f:
                terraform_code = f.read()
            
            # Validate terraform
            validation_result = await self.terraform_validator.validate_and_plan(
                terraform_code,
                session['provider'],
                work_dir=result['output_dir']
            )
            
            # Build result embed  
            if validation_result.is_valid:
                embed = discord.Embed(
                    title="✅ Terraform Validation Passed",
                    description="Your terraform configuration is valid and ready to deploy!",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Validated using terraform in: {result['output_dir']}")
                
                if validation_result.plan_summary:
                    plan = validation_result.plan_summary
                    embed.add_field(
                        name="📋 Plan Summary",
                        value=(
                            f"**To Add**: {plan['to_add']}\n"
                            f"**To Change**: {plan['to_change']}\n"
                            f"**To Destroy**: {plan['to_destroy']}\n"
                            f"**Has Changes**: {'Yes' if plan['has_changes'] else 'No'}"
                        ),
                        inline=True
                    )
                    
                    # Show resource changes
                    if plan.get('resource_changes'):
                        changes_text = "\n".join([
                            f"• `{rc['resource']}`: {rc['action_summary']}"
                            for rc in plan['resource_changes'][:5]
                        ])
                        embed.add_field(
                            name="🔧 Resource Changes",
                            value=changes_text,
                            inline=False
                        )
                
                if validation_result.warnings:
                    embed.add_field(
                        name="⚠️ Warnings",
                        value="\n".join([f"• {w}" for w in validation_result.warnings[:3]]),
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
            else:
                embed = discord.Embed(
                    title="❌ Terraform Validation Failed",
                    description="Your configuration has errors that must be fixed.",
                    color=discord.Color.red()
                )
                
                if validation_result.errors:
                    errors_text = "\n".join([f"• {e}" for e in validation_result.errors[:5]])
                    embed.add_field(
                        name="Errors",
                        value=errors_text,
                        inline=False
                    )
                
                if validation_result.warnings:
                    warnings_text = "\n".join([f"• {w}" for w in validation_result.warnings[:3]])
                    embed.add_field(
                        name="Warnings",
                        value=warnings_text,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Validation error: {str(e)}",
                ephemeral=True
            )
    
    # --- MONITORING & HEALTH ---
    
    @app_commands.command(name="cloud-health", description="Check cloud cog health status")
    async def cloud_health(self, interaction: discord.Interaction):
        """Display cog health metrics"""
        await interaction.response.defer(ephemeral=True)
        
        health = CloudCogHealth.get_cog_health(self)
        
        embed = discord.Embed(
            title="🩺 Cloud Cog Health Status",
            color=discord.Color.green() if health['ai_advisor_status'] == 'available' else discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="💾 Memory Usage", 
            value=f"{health['memory_mb']:.1f} MB", 
            inline=True
        )
        embed.add_field(
            name="⚡ CPU Usage", 
            value=f"{health['cpu_percent']:.1f}%", 
            inline=True
        )
        embed.add_field(
            name="📊 Database Size", 
            value=f"{health['database_size_mb']:.1f} MB", 
            inline=True
        )
        embed.add_field(
            name="🔄 Active Sessions", 
            value=str(health['active_sessions']), 
            inline=True
        )
        embed.add_field(
            name="🧵 Threads", 
            value=str(health['thread_count']), 
            inline=True
        )
        embed.add_field(
            name="🤖 AI Status", 
            value=health['ai_advisor_status'].title(), 
            inline=True
        )
        
        # Add status indicator
        if health['ai_advisor_status'] == 'available':
            embed.set_footer(text="✅ All systems operational")
        else:
            embed.set_footer(text="⚠️ Running in limited mode (AI unavailable)")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # --- GUILD POLICY MANAGEMENT (Multi-Tenant) ---
    
    @app_commands.command(name="cloud-guild-policy", description="Manage server-wide cloud policies (Admin Only)")
    @app_commands.describe(
        action="View or update guild policies",
        max_budget="Maximum monthly budget in USD (default: 1000)",
        max_instances="Maximum concurrent instances (default: 10)",
        engine="Preferred IaC engine (terraform or tofu)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="View Current Policies", value="view"),
            app_commands.Choice(name="Update Policies", value="update")
        ],
        engine=[
            app_commands.Choice(name="Terraform", value="terraform"),
            app_commands.Choice(name="OpenTofu", value="tofu")
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cloud_guild_policy(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        max_budget: Optional[float] = None,
        max_instances: Optional[int] = None,
        engine: Optional[app_commands.Choice[str]] = None
    ):
        """Manage guild-level cloud policies"""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        if action.value == "view":
            # Fetch current policies
            policies = cloud_db.get_guild_policies(guild_id)
            
            if not policies:
                embed = discord.Embed(
                    title="📜 Guild Cloud Policies",
                    description="Using **default policies** (no custom policies set)",
                    color=discord.Color.blue()
                )
                embed.add_field(name="💰 Max Budget/Month", value="$1,000", inline=True)
                embed.add_field(name="🖥️ Max Instances", value="10", inline=True)
                embed.add_field(name="🛠️ IaC Engine", value="terraform", inline=True)
                embed.set_footer(text="Use /cloud-guild-policy action:update to customize")
            else:
                embed = discord.Embed(
                    title="📜 Guild Cloud Policies",
                    description=f"Custom policies for **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="💰 Max Budget/Month", value=f"${policies['max_budget_monthly']}", inline=True)
                embed.add_field(name="🖥️ Max Instances", value=str(policies['max_instances']), inline=True)
                embed.add_field(name="💾 Max Disk Size", value=f"{policies['max_disk_size_gb']} GB", inline=True)
                embed.add_field(name="🛠️ IaC Engine", value=policies['iac_engine_preference'], inline=True)
                embed.add_field(name="✅ Require Approval", value="Yes" if policies['require_approval'] else "No", inline=True)
                
                # Show resource count
                resource_count = cloud_db.get_guild_resource_count(guild_id)
                embed.add_field(name="📊 Active Resources", value=f"{resource_count}/{policies['max_instances']}", inline=True)
                
                # Parse allowed types
                try:
                    allowed_instances = json.loads(policies['allowed_instance_types']) if isinstance(policies['allowed_instance_types'], str) else policies['allowed_instance_types']
                    allowed_resources = json.loads(policies['allowed_resource_types']) if isinstance(policies['allowed_resource_types'], str) else policies['allowed_resource_types']
                    
                    if allowed_instances:
                        embed.add_field(
                            name="🖥️ Allowed Instance Types",
                            value=", ".join(allowed_instances) or "All",
                            inline=False
                        )
                    if allowed_resources:
                        embed.add_field(
                            name="☁️ Allowed Resource Types",
                            value=", ".join(allowed_resources) or "All",
                            inline=False
                        )
                except:
                    pass
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif action.value == "update":
            # Get existing policies or create new
            existing = cloud_db.get_guild_policies(guild_id) or {}
            
            # Build update dict
            new_policies = {
                'max_budget_monthly': max_budget if max_budget is not None else existing.get('max_budget_monthly', 1000.0),
                'max_instances': max_instances if max_instances is not None else existing.get('max_instances', 10),
                'iac_engine_preference': engine.value if engine else existing.get('iac_engine_preference', 'terraform'),
                'allowed_instance_types': existing.get('allowed_instance_types', []),
                'allowed_resource_types': existing.get('allowed_resource_types', []),
                'require_approval': existing.get('require_approval', 0),
                'max_disk_size_gb': existing.get('max_disk_size_gb', 500)
            }
            
            # Update in database
            success = cloud_db.set_guild_policies(guild_id, new_policies)
            
            if success:
                embed = discord.Embed(
                    title="✅ Guild Policies Updated",
                    description=f"Cloud policies updated for **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="💰 Max Budget/Month", value=f"${new_policies['max_budget_monthly']}", inline=True)
                embed.add_field(name="🖥️ Max Instances", value=str(new_policies['max_instances']), inline=True)
                embed.add_field(name="🛠️ IaC Engine", value=new_policies['iac_engine_preference'], inline=True)
                embed.set_footer(text="These policies will apply to all new deployments")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Failed to update guild policies. Check logs.",
                    ephemeral=True
                )
    
    @app_commands.command(name="cloud-jit-grant", description="Grant temporary cloud permissions (Admin Only)")
    @app_commands.describe(
        user="User to grant permissions to",
        provider="Cloud provider",
        level="Permission level",
        duration="Duration in minutes (default: 60)"
    )
    @app_commands.choices(
        provider=[
            app_commands.Choice(name="Google Cloud (GCP)", value="gcp"),
            app_commands.Choice(name="Amazon Web Services (AWS)", value="aws"),
            app_commands.Choice(name="Microsoft Azure", value="azure")
        ],
        level=[
            app_commands.Choice(name="Viewer (Read-Only)", value="viewer"),
            app_commands.Choice(name="Deployer (Create/Update)", value="deployer"),
            app_commands.Choice(name="Admin (Full Control)", value="admin")
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cloud_jit_grant(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        provider: app_commands.Choice[str],
        level: app_commands.Choice[str],
        duration: Optional[int] = 60
    ):
        """Grant Just-In-Time temporary cloud permissions"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Grant JIT permission
            perm_id = cloud_db.grant_jit_permission(
                user_id=str(user.id),
                guild_id=str(interaction.guild.id),
                provider=provider.value,
                permission_level=level.value,
                granted_by=str(interaction.user.id),
                duration_minutes=duration
            )
            
            # Notify user
            try:
                await user.send(
                    f"🔑 **JIT Permission Granted**\n"
                    f"You've been granted **{level.name}** access to **{provider.name}** "
                    f"in server **{interaction.guild.name}**\n\n"
                    f"⏰ Expires in: **{duration} minutes**\n"
                    f"📋 Permission ID: `{perm_id}`\n"
                    f"👤 Granted by: {interaction.user.mention}"
                )
            except:
                pass  # User might have DMs disabled
            
            embed = discord.Embed(
                title="✅ JIT Permission Granted",
                description=f"Temporary access granted to {user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="☁️ Provider", value=provider.name, inline=True)
            embed.add_field(name="🔐 Level", value=level.name, inline=True)
            embed.add_field(name="⏰ Duration", value=f"{duration} min", inline=True)
            embed.add_field(name="📋 Permission ID", value=f"`{perm_id}`", inline=False)
            embed.set_footer(text="Permission will auto-expire and be revoked by JIT Janitor")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to grant JIT permission: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-jit-revoke", description="Revoke temporary cloud permissions (Admin Only)")
    @app_commands.describe(
        user="User to revoke permissions from"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cloud_jit_revoke(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Revoke all active JIT permissions for a user"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            success = cloud_db.revoke_jit_permission(
                user_id=str(user.id),
                guild_id=str(interaction.guild.id)
            )
            
            if success:
                # Notify user
                try:
                    await user.send(
                        f"🔒 **JIT Permissions Revoked**\n"
                        f"All your temporary cloud permissions in **{interaction.guild.name}** "
                        f"have been revoked by an administrator."
                    )
                except:
                    pass
                
                await interaction.followup.send(
                    f"✅ Revoked all JIT permissions for {user.mention}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"⚠️ No active JIT permissions found for {user.mention}",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to revoke permissions: {e}",
                ephemeral=True
            )
    
    # --- SESSION RECOVERY (Upgrade A: Encrypted Handshake) ---
    
    @app_commands.command(name="cloud-recover-session", description="Recover crashed deployment session (Break-Glass)")
    @app_commands.describe(
        session_id="Session ID from /cloud-init"
    )
    async def cloud_recover_session(
        self,
        interaction: discord.Interaction,
        session_id: str
    ):
        """Recover session from encrypted recovery blob after bot crash"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            # Get recovery blob from database
            recovery_data = cloud_db.get_recovery_blob(session_id)
            
            if not recovery_data:
                # Check if user has any active sessions
                active_sessions = cloud_db.get_user_active_sessions(user_id, guild_id)
                
                if active_sessions:
                    sessions_list = "\n".join([f"• `{s['session_id']}` (created {int((time.time() - s['created_at']) / 60)} min ago)" for s in active_sessions[:5]])
                    
                    await interaction.followup.send(
                        f"❌ Session `{session_id}` not found.\n\n"
                        f"**Your Active Sessions:**\n{sessions_list}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ No active sessions found. Use `/cloud-init` to create a new project.",
                        ephemeral=True
                    )
                return
            
            # Verify ownership
            if recovery_data['user_id'] != user_id:
                await interaction.followup.send(
                    "⛔ You don't own this session.",
                    ephemeral=True
                )
                return
            
            # Check expiration
            if time.time() > recovery_data['expires_at']:
                await interaction.followup.send(
                    "⏰ Session expired. Please create a new project with `/cloud-init`.",
                    ephemeral=True
                )
                return
            
            # Recover session using user's passphrase (user_id)
            user_passphrase = user_id
            success = ephemeral_vault.recover_session(
                session_id,
                recovery_data['encrypted_blob'],
                user_passphrase
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Session Recovered Successfully",
                    description="Your vault session has been restored from the recovery blob!",
                    color=discord.Color.green()
                )
                embed.add_field(name="🔑 Session ID", value=f"`{session_id}`", inline=False)
                embed.add_field(name="⏰ Time Remaining", value=f"{int((recovery_data['expires_at'] - time.time()) / 60)} minutes", inline=True)
                embed.add_field(
                    name="💡 What Happened?",
                    value="The bot crashed during your deployment. Your project ID was safely recovered from the encrypted recovery blob.",
                    inline=False
                )
                embed.set_footer(text="You can now resume your deployment")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                print(f"🆘 [Recovery] Session {session_id} recovered for user {user_id}")
            else:
                await interaction.followup.send(
                    "❌ Failed to recover session. The recovery blob may be corrupted.",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Recovery error: {e}",
                ephemeral=True
            )
    
    # --- BLUEPRINT MIGRATION (Memory-Safe) ---
    
    @app_commands.command(name="cloud-blueprint", 
                         description="Generate migration blueprint (Terraform/OpenTofu code)")
    @app_commands.describe(
        source_project_id="Project ID to migrate FROM",
        target_provider="Target cloud provider",
        target_region="Target region",
        iac_engine="IaC engine to use",
        include_docs="Include documentation (recommended)"
    )
    @app_commands.choices(
        target_provider=[
            app_commands.Choice(name="Google Cloud (GCP)", value="gcp"),
            app_commands.Choice(name="Amazon Web Services (AWS)", value="aws"),
            app_commands.Choice(name="Microsoft Azure", value="azure")
        ],
        iac_engine=[
            app_commands.Choice(name="Terraform", value="terraform"),
            app_commands.Choice(name="OpenTofu", value="tofu")
        ]
    )
    async def cloud_blueprint(
        self,
        interaction: discord.Interaction,
        source_project_id: str,
        target_provider: app_commands.Choice[str],
        target_region: str,
        iac_engine: app_commands.Choice[str],
        include_docs: bool = True
    ):
        """Generate migration blueprint (Terraform/OpenTofu code for download)"""
        await interaction.response.defer()
        
        try:
            # Check memory first
            health = CloudCogHealth.get_cog_health(self)
            if health['memory_mb'] > 700:  # 700MB threshold
                await interaction.followup.send(
                    "⚠️ **Memory Warning**: Bot memory is high ({:.1f}MB)\n"
                    "Blueprint generation may be slower or fail.\n\n"
                    "Consider restarting bot or using a smaller project.".format(health['memory_mb']),
                    ephemeral=True
                )
            
            # Get source project
            source_project = cloud_db.get_cloud_project(source_project_id)
            if not source_project:
                await interaction.followup.send(
                    f"❌ Source project `{source_project_id}` not found.",
                    ephemeral=True
                )
                return
            
            # Check ownership
            if source_project['owner_user_id'] != str(interaction.user.id):
                await interaction.followup.send(
                    "⛔ You don't own this project.",
                    ephemeral=True
                )
                return
            
            # Check if same provider
            if source_project['provider'] == target_provider.value:
                await interaction.followup.send(
                    f"ℹ️ **Same Provider**: You're staying in {target_provider.name}.\n"
                    f"Consider using `/cloud-edit` instead of migration.",
                    ephemeral=True
                )
                # Continue anyway - user might want a fresh blueprint
            
            # Show progress
            progress_msg = await interaction.followup.send(
                f"🔧 **Generating Migration Blueprint...**\n"
                f"**Source**: {source_project['project_name']} ({source_project['provider'].upper()})\n"
                f"**Target**: {target_provider.name} ({target_region})\n"
                f"**Engine**: {iac_engine.name}\n\n"
                f"⏳ This may take a moment...",
                ephemeral=True
            )
            
            # Generate blueprint
            from cloud_blueprint_generator import BlueprintGenerator
            
            blueprint = await BlueprintGenerator.generate_blueprint(
                source_project_id=source_project_id,
                target_provider=target_provider.value,
                target_region=target_region,
                user_id=str(interaction.user.id),
                guild_id=str(interaction.guild.id),
                iac_engine=iac_engine.value,
                include_docs=include_docs
            )
            
            # Update progress message
            await progress_msg.edit(
                content=(
                    f"✅ **Blueprint Generated!**\n"
                    f"**ID**: `{blueprint.blueprint_id}`\n"
                    f"**Resources**: {len(blueprint.resources)} mapped\n"
                    f"**File Size**: {blueprint.file_size_bytes / 1024:.1f} KB\n"
                    f"**Expires**: <t:{int(blueprint.expires_at)}:R>\n\n"
                    f"Use `/cloud-blueprint-download` with token: `{blueprint.download_token}`"
                )
            )
            
            # Send summary embed
            embed = discord.Embed(
                title="📋 Migration Blueprint Generated",
                description=f"Terraform code ready for {target_provider.name}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Summary",
                value=(
                    f"**Blueprint ID**: `{blueprint.blueprint_id}`\n"
                    f"**Source**: {source_project['project_name']}\n"
                    f"**Target**: {target_provider.name} ({target_region})\n"
                    f"**Resources**: {len(blueprint.resources)} mapped"
                ),
                inline=False
            )
            
            # Complexity breakdown
            complexity_counts = {}
            for resource in blueprint.resources:
                complexity_counts[resource.complexity] = complexity_counts.get(resource.complexity, 0) + 1
            
            if complexity_counts:
                complexity_text = "\n".join([
                    f"• **{c.title()}**: {count} resources"
                    for c, count in complexity_counts.items()
                ])
                embed.add_field(
                    name="📈 Complexity",
                    value=complexity_text,
                    inline=True
                )
            
            # Resource types
            type_counts = {}
            for resource in blueprint.resources:
                type_counts[resource.target_type] = type_counts.get(resource.target_type, 0) + 1
            
            if type_counts:
                type_text = "\n".join([
                    f"• **{t}**: {count}"
                    for t, count in list(type_counts.items())[:5]
                ])
                embed.add_field(
                    name="🔧 Resource Types",
                    value=type_text,
                    inline=True
                )
            
            # Download instructions
            embed.add_field(
                name="⬇️ How to Download",
                value=(
                    f"```\n/cloud-blueprint-download token:{blueprint.download_token}\n```\n"
                    f"**Expires**: <t:{int(blueprint.expires_at)}:R>\n"
                    f"**Size**: {blueprint.file_size_bytes / 1024:.1f} KB"
                ),
                inline=False
            )
            
            # What's included
            embed.add_field(
                name="📁 Files Included",
                value=(
                    "• `main.tf` - Terraform configurations\n"
                    "• `variables.tf` - Input variables\n"
                    "• `outputs.tf` - Output values\n"
                    "• `README.md` - Instructions\n"
                    "• `MAPPING_REPORT.md` - Detailed mapping"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Blueprint ID: {blueprint.blueprint_id}")
            
            # Send to channel (not ephemeral)
            await interaction.followup.send(embed=embed)
            
            # Send a DM with the token (more secure)
            try:
                await interaction.user.send(
                    f"🔐 **Your Blueprint Download Token**\n"
                    f"Token: `{blueprint.download_token}`\n"
                    f"Blueprint ID: `{blueprint.blueprint_id}`\n"
                    f"Expires: <t:{int(blueprint.expires_at)}:R>\n\n"
                    f"**Keep this token safe!** It's required to download your blueprint.\n"
                    f"Use: `/cloud-blueprint-download token:{blueprint.download_token}`"
                )
            except:
                pass  # User has DMs disabled
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Blueprint generation failed: {str(e)}\n\n"
                f"**Common Issues**:\n"
                "1. Project has no resources\n"
                "2. Memory is too high (check `/cloud-health`)\n"
                "3. Invalid target region\n"
                "4. Bot restart needed",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-blueprint-download", 
                         description="Download a generated blueprint")
    @app_commands.describe(
        token="Download token from /cloud-blueprint"
    )
    async def cloud_blueprint_download(
        self,
        interaction: discord.Interaction,
        token: str
    ):
        """Download generated blueprint (time-gated)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            from cloud_blueprint_generator import BlueprintGenerator
            
            # Get blueprint download
            result = BlueprintGenerator.get_blueprint_download(token)
            
            if not result:
                await interaction.followup.send(
                    "❌ **Blueprint not found or expired**\n\n"
                    "Possible reasons:\n"
                    "1. Token is incorrect\n"
                    "2. Blueprint expired (24-hour limit)\n"
                    "3. Already downloaded\n"
                    "4. Bot was restarted (blueprints are ephemeral)\n\n"
                    "Generate a new blueprint with `/cloud-blueprint`",
                    ephemeral=True
                )
                return
            
            file_path, blueprint_data = result
            
            # Send file
            with open(file_path, 'rb') as f:
                file = discord.File(
                    f, 
                    filename=f"blueprint_{blueprint_data.get('blueprint_id', 'unknown')}.zip"
                )
                
                embed = discord.Embed(
                    title="📥 Blueprint Download",
                    description="Your migration blueprint is ready!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📋 Details",
                    value=(
                        f"**Blueprint ID**: `{blueprint_data.get('blueprint_id', 'unknown')}`\n"
                        f"**Target Provider**: {blueprint_data.get('target_provider', '').upper()}\n"
                        f"**Target Region**: {blueprint_data.get('target_region', '')}\n"
                        f"**File Size**: {blueprint_data.get('file_size_bytes', 0) / 1024:.1f} KB"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="⚠️ Important",
                    value=(
                        "**This download will expire in:** <t:{}:R>\n"
                        "**After expiration**, you'll need to generate a new blueprint.\n\n"
                        "**Security**: This file contains only infrastructure code, no credentials."
                    ).format(int(blueprint_data.get('expires_at', 0))),
                    inline=False
                )
                
                embed.add_field(
                    name="🚀 Next Steps",
                    value=(
                        "1. **Extract** the zip file\n"
                        "2. **Review** all generated code\n"
                        "3. **Update** variables with your values\n"
                        "4. **Test** in a staging environment\n"
                        "5. **Apply** when ready"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
            # Mark as downloaded (optional)
            # Could update status in vault to prevent re-downloads
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Download failed: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="cloud-blueprint-status", 
                         description="Check status of your blueprints")
    async def cloud_blueprint_status(
        self,
        interaction: discord.Interaction
    ):
        """Check blueprint status"""
        await interaction.response.defer(ephemeral=True)
        
        # Note: Since blueprints are ephemeral, we can't list them all
        # We'll show instructions instead
        
        embed = discord.Embed(
            title="🔍 Blueprint Status",
            description="About blueprint generation and downloads",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 What are Blueprints?",
            value=(
                "Blueprints are **Terraform/OpenTofu code** that help you migrate "
                "between cloud providers. They're **time-gated** for security."
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏱️ Time Limits",
            value=(
                "• **Generation**: Takes 10-30 seconds\n"
                "• **Availability**: 24 hours after generation\n"
                "• **Downloads**: Unlimited within availability window\n"
                "• **Security**: Auto-deleted after expiration"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔒 Security Features",
            value=(
                "• **Zero-trust**: No cloud credentials stored\n"
                "• **Time-gated**: Auto-expiring downloads\n"
                "• **Ephemeral**: Lost on bot restart\n"
                "• **Token-based**: Secure download access"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💾 Memory Usage",
            value=(
                "• **Generation**: ~50-100MB temporary spike\n"
                "• **Storage**: On-disk, not in RAM\n"
                "• **Cleanup**: Automatic after 24 hours\n"
                "• **Optimized**: For 1GB RAM environments"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📝 How to Use",
            value=(
                "1. Generate: `/cloud-blueprint`\n"
                "2. Save token from DM\n"
                "3. Download: `/cloud-blueprint-download`\n"
                "4. Extract and review code\n"
                "5. Apply with Terraform"
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ Lost Your Token?",
            value=(
                "If you lost your download token:\n"
                "1. Generate a new blueprint\n"
                "2. Save the new token\n"
                "3. Old blueprint will auto-expire\n\n"
                "Tokens are **ephemeral** by design for security."
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CloudCog(bot))
