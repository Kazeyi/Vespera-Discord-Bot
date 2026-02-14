"""
Enhanced Resource Configuration Modals

Provider-specific interactive forms with validation.
"""

import discord
from discord import ui
from typing import Optional, Literal


class VMResourceModal(ui.Modal, title="Configure Virtual Machine"):
    """Modal for configuring compute VMs"""
    
    vm_name = ui.TextInput(
        label="VM Name",
        placeholder="my-server-01",
        required=True,
        max_length=63
    )
    
    machine_type = ui.TextInput(
        label="Machine Type",
        placeholder="e2-medium (GCP), t3.small (AWS), Standard_B2s (Azure)",
        required=True
    )
    
    cpu_cores = ui.TextInput(
        label="CPU Cores",
        placeholder="2 (optional - some types have fixed CPUs)",
        required=False,
        max_length=3
    )
    
    memory_gb = ui.TextInput(
        label="Memory (GB)",
        placeholder="4 (optional - some types have fixed memory)",
        required=False,
        max_length=4
    )
    
    disk_size_gb = ui.TextInput(
        label="Disk Size (GB)",
        placeholder="100",
        default="100",
        required=False,
        max_length=5
    )
    
    def __init__(self, session_id: str, orchestrator, provider: str):
        super().__init__()
        self.session_id = session_id
        self.orchestrator = orchestrator
        self.provider = provider
        
        # Update placeholder based on provider
        if provider == 'gcp':
            self.machine_type.placeholder = "e2-micro, e2-small, e2-medium, e2-standard-2, n1-standard-1"
        elif provider == 'aws':
            self.machine_type.placeholder = "t3.micro, t3.small, t3.medium, m5.large, c5.large"
        elif provider == 'azure':
            self.machine_type.placeholder = "Standard_B1s, Standard_B2s, Standard_D2s_v3"
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        
        # Build config
        config = {
            'name': self.vm_name.value,
            'machine_type': self.machine_type.value,
        }
        
        # Add optional fields
        if self.cpu_cores.value:
            try:
                config['cpu_cores'] = int(self.cpu_cores.value)
            except ValueError:
                pass
        
        if self.memory_gb.value:
            try:
                config['memory_gb'] = int(self.memory_gb.value)
            except ValueError:
                pass
        
        if self.disk_size_gb.value:
            try:
                config['disk_size_gb'] = int(self.disk_size_gb.value)
            except ValueError:
                config['disk_size_gb'] = 100
        
        # Add to session
        success = self.orchestrator.add_resource(
            self.session_id,
            'compute_vm',
            config
        )
        
        if success:
            # Get cost estimate
            from ..core.cost_estimator import CostEstimator
            estimate = CostEstimator.estimate_resource(
                self.provider,
                'compute_vm',
                config
            )
            
            # Show confirmation with cost
            embed = discord.Embed(
                title="✅ VM Added",
                description=f"**{config['name']}** added to deployment",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Configuration",
                value=f"Type: `{config['machine_type']}`\nDisk: {config.get('disk_size_gb', 100)} GB",
                inline=False
            )
            
            embed.add_field(
                name="💰 Estimated Cost",
                value=f"${estimate.hourly_cost:.4f}/hour\n${estimate.monthly_cost:.2f}/month",
                inline=False
            )
            
            if estimate.recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value="\n".join(estimate.recommendations[:2]),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to add VM. Session may be locked or expired.",
                ephemeral=True
            )


class DatabaseResourceModal(ui.Modal, title="Configure Database"):
    """Modal for configuring databases"""
    
    db_name = ui.TextInput(
        label="Database Name",
        placeholder="prod-db",
        required=True,
        max_length=63
    )
    
    db_type = ui.TextInput(
        label="Database Type",
        placeholder="postgresql, mysql, sqlserver, etc.",
        required=True
    )
    
    instance_type = ui.TextInput(
        label="Instance Type",
        placeholder="db-f1-micro (GCP), db.t3.micro (AWS), Basic (Azure)",
        required=True
    )
    
    storage_gb = ui.TextInput(
        label="Storage (GB)",
        placeholder="20",
        default="20",
        required=False
    )
    
    backup_retention_days = ui.TextInput(
        label="Backup Retention (days)",
        placeholder="7",
        default="7",
        required=False,
        max_length=3
    )
    
    def __init__(self, session_id: str, orchestrator, provider: str):
        super().__init__()
        self.session_id = session_id
        self.orchestrator = orchestrator
        self.provider = provider
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        
        config = {
            'name': self.db_name.value,
            'database_type': self.db_type.value,
            'machine_type': self.instance_type.value,
        }
        
        if self.storage_gb.value:
            try:
                config['storage_gb'] = int(self.storage_gb.value)
            except ValueError:
                config['storage_gb'] = 20
        
        if self.backup_retention_days.value:
            try:
                config['backup_retention_days'] = int(self.backup_retention_days.value)
            except ValueError:
                config['backup_retention_days'] = 7
        
        success = self.orchestrator.add_resource(
            self.session_id,
            'database',
            config
        )
        
        if success:
            from ..core.cost_estimator import CostEstimator
            estimate = CostEstimator.estimate_resource(
                self.provider,
                'database',
                config
            )
            
            embed = discord.Embed(
                title="✅ Database Added",
                description=f"**{config['name']}** ({config['database_type']}) added",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Configuration",
                value=f"Type: `{config['machine_type']}`\nStorage: {config.get('storage_gb', 20)} GB\nBackups: {config.get('backup_retention_days', 7)} days",
                inline=False
            )
            
            embed.add_field(
                name="💰 Estimated Cost",
                value=f"${estimate.monthly_cost:.2f}/month",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to add database.",
                ephemeral=True
            )


class VPCResourceModal(ui.Modal, title="Configure VPC/Network"):
    """Modal for configuring VPCs"""
    
    vpc_name = ui.TextInput(
        label="VPC/Network Name",
        placeholder="production-vpc",
        required=True,
        max_length=63
    )
    
    cidr_block = ui.TextInput(
        label="CIDR Block",
        placeholder="10.0.0.0/16",
        required=True
    )
    
    subnets = ui.TextInput(
        label="Subnets (comma-separated CIDRs)",
        placeholder="10.0.1.0/24, 10.0.2.0/24",
        required=False,
        style=discord.TextStyle.paragraph
    )
    
    enable_dns = ui.TextInput(
        label="Enable DNS (yes/no)",
        placeholder="yes",
        default="yes",
        required=False,
        max_length=3
    )
    
    def __init__(self, session_id: str, orchestrator, provider: str):
        super().__init__()
        self.session_id = session_id
        self.orchestrator = orchestrator
        self.provider = provider
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        
        config = {
            'name': self.vpc_name.value,
            'cidr_block': self.cidr_block.value,
            'enable_dns': self.enable_dns.value.lower() in ['yes', 'true', 'y'],
        }
        
        if self.subnets.value:
            config['subnets'] = [s.strip() for s in self.subnets.value.split(',')]
        
        success = self.orchestrator.add_resource(
            self.session_id,
            'vpc',
            config
        )
        
        if success:
            embed = discord.Embed(
                title="✅ VPC Added",
                description=f"**{config['name']}** added",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Configuration",
                value=f"CIDR: `{config['cidr_block']}`\nSubnets: {len(config.get('subnets', []))}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to add VPC.",
                ephemeral=True
            )


class StorageBucketModal(ui.Modal, title="Configure Storage Bucket"):
    """Modal for configuring storage buckets"""
    
    bucket_name = ui.TextInput(
        label="Bucket Name",
        placeholder="my-data-bucket",
        required=True,
        max_length=63
    )
    
    storage_class = ui.TextInput(
        label="Storage Class",
        placeholder="standard, nearline (GCP), s3-standard (AWS), hot (Azure)",
        required=True
    )
    
    versioning = ui.TextInput(
        label="Enable Versioning (yes/no)",
        placeholder="yes",
        default="no",
        required=False,
        max_length=3
    )
    
    lifecycle_days = ui.TextInput(
        label="Lifecycle Delete After (days, 0=never)",
        placeholder="0",
        default="0",
        required=False,
        max_length=4
    )
    
    def __init__(self, session_id: str, orchestrator, provider: str):
        super().__init__()
        self.session_id = session_id
        self.orchestrator = orchestrator
        self.provider = provider
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        
        config = {
            'name': self.bucket_name.value,
            'storage_class': self.storage_class.value,
            'versioning': self.versioning.value.lower() in ['yes', 'true', 'y'],
        }
        
        if self.lifecycle_days.value:
            try:
                days = int(self.lifecycle_days.value)
                if days > 0:
                    config['lifecycle_delete_days'] = days
            except ValueError:
                pass
        
        success = self.orchestrator.add_resource(
            self.session_id,
            'storage_bucket',
            config
        )
        
        if success:
            embed = discord.Embed(
                title="✅ Storage Bucket Added",
                description=f"**{config['name']}** added",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Configuration",
                value=f"Class: `{config['storage_class']}`\nVersioning: {config['versioning']}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to add storage bucket.",
                ephemeral=True
            )


# Modal factory
def create_resource_modal(
    resource_type: str,
    session_id: str,
    orchestrator,
    provider: str
) -> Optional[ui.Modal]:
    """
    Factory function to create appropriate modal for resource type
    
    Args:
        resource_type: Type of resource
        session_id: Session ID
        orchestrator: CloudOrchestrator instance
        provider: Cloud provider
    
    Returns:
        Appropriate modal or None
    """
    modal_map = {
        'compute_vm': VMResourceModal,
        'vm': VMResourceModal,
        'database': DatabaseResourceModal,
        'db': DatabaseResourceModal,
        'vpc': VPCResourceModal,
        'network': VPCResourceModal,
        'storage_bucket': StorageBucketModal,
        'bucket': StorageBucketModal,
    }
    
    modal_class = modal_map.get(resource_type)
    
    if modal_class:
        return modal_class(session_id, orchestrator, provider)
    
    return None
