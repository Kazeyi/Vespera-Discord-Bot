# --- Cloud Migration Blueprint Generator ---
"""
Generate Terraform/OpenTofu blueprints for cloud migration
Memory-optimized: No real APIs, only configuration mapping
"""

import os
import json
import time
import hashlib
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import cloud_database as cloud_db
from cloud_security import ephemeral_vault


@dataclass
class BlueprintResource:
    """Blueprint resource mapping"""
    source_name: str
    source_type: str
    source_provider: str
    target_type: str
    target_provider: str
    tf_config: Dict  # Terraform configuration
    mapping_notes: List[str]
    complexity: str  # low/medium/high


@dataclass
class Blueprint:
    """Complete migration blueprint"""
    blueprint_id: str
    source_project_id: str
    target_provider: str
    target_region: str
    iac_engine: str  # terraform or tofu
    resources: List[BlueprintResource]
    created_at: float
    expires_at: float
    download_token: str
    file_size_bytes: int = 0
    status: str = "generated"  # generated, downloaded, expired


class BlueprintGenerator:
    """Generate migration blueprints (Terraform/OpenTofu code)"""
    
    # Resource type mappings for blueprint generation
    RESOURCE_TEMPLATES = {
        # AWS Terraform templates
        "aws": {
            "vm": """
resource "aws_instance" "{resource_name}" {{
  ami           = "{ami_id}"
  instance_type = "{instance_type}"
  
  tags = {{
    Name = "{resource_name}"
    Source = "migrated-from-{source_provider}"
    MigrationDate = "{timestamp}"
  }}
}}
""",
            "database": """
resource "aws_db_instance" "{resource_name}" {{
  identifier     = "{resource_name}"
  instance_class = "{instance_class}"
  engine         = "{engine}"
  allocated_storage = {storage_gb}
  
  tags = {{
    Name = "{resource_name}"
    Source = "migrated-from-{source_provider}"
  }}
}}
""",
            "bucket": """
resource "aws_s3_bucket" "{resource_name}" {{
  bucket = "{resource_name}"
  
  tags = {{
    Name = "{resource_name}"
    Source = "migrated-from-{source_provider}"
  }}
}}
"""
        },
        # GCP Terraform templates
        "gcp": {
            "vm": """
resource "google_compute_instance" "{resource_name}" {{
  name         = "{resource_name}"
  machine_type = "{machine_type}"
  zone         = "{zone}"
  
  boot_disk {{
    initialize_params {{
      size = {disk_size_gb}
    }}
  }}
  
  tags = ["migrated-from-{source_provider}"]
  
  metadata = {{
    migration-source = "{source_provider}"
    migration-date = "{timestamp}"
  }}
}}
""",
            "database": """
resource "google_sql_database_instance" "{resource_name}" {{
  name             = "{resource_name}"
  database_version = "{database_version}"
  
  settings {{
    tier = "{tier}"
  }}
}}
""",
            "bucket": """
resource "google_storage_bucket" "{resource_name}" {{
  name     = "{resource_name}"
  location = "{location}"
  
  labels = {{
    source = "{source_provider}"
  }}
}}
"""
        },
        # Azure Terraform templates
        "azure": {
            "vm": """
resource "azurerm_virtual_machine" "{resource_name}" {{
  name                  = "{resource_name}"
  location              = "{location}"
  resource_group_name   = "{resource_group}"
  vm_size               = "{vm_size}"
  
  storage_os_disk {{
    name              = "{resource_name}-os"
    caching           = "ReadWrite"
    create_option     = "FromImage"
  }}
  
  tags = {{
    source = "{source_provider}"
  }}
}}
""",
            "database": """
resource "azurerm_sql_database" "{resource_name}" {{
  name                = "{resource_name}"
  resource_group_name = "{resource_group}"
  location            = "{location}"
  
  tags = {{
    source = "{source_provider}"
  }}
}}
""",
            "bucket": """
resource "azurerm_storage_account" "{resource_name}" {{
  name                     = "{resource_name}"
  resource_group_name      = "{resource_group}"
  location                 = "{location}"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  tags = {{
    source = "{source_provider}"
  }}
}}
"""
        }
    }
    
    @staticmethod
    async def generate_blueprint(
        source_project_id: str,
        target_provider: str,
        target_region: str,
        user_id: str,
        guild_id: str,
        iac_engine: str = "terraform",
        include_docs: bool = True
    ) -> Blueprint:
        """
        Generate migration blueprint (Terraform/OpenTofu code)
        
        Returns:
            Blueprint object with generated code
        """
        # Generate blueprint ID and token
        blueprint_id = f"blueprint-{hashlib.md5(f'{source_project_id}{target_provider}{time.time()}'.encode()).hexdigest()[:12]}"
        download_token = hashlib.sha256(f"{blueprint_id}{user_id}{time.time()}".encode()).hexdigest()[:16]
        
        # Get source project
        source_project = cloud_db.get_cloud_project(source_project_id)
        if not source_project:
            raise Exception(f"Source project {source_project_id} not found")
        
        source_provider = source_project['provider']
        
        # Get source resources
        source_resources = cloud_db.get_project_resources(source_project_id)
        if not source_resources:
            raise Exception(f"No resources found in project {source_project_id}")
        
        # Map and generate resources
        blueprint_resources = []
        for resource in source_resources[:20]:  # Limit to 20 resources for memory
            blueprint_resource = BlueprintGenerator._generate_resource_blueprint(
                resource=resource,
                source_provider=source_provider,
                target_provider=target_provider,
                target_region=target_region
            )
            if blueprint_resource:
                blueprint_resources.append(blueprint_resource)
        
        # Create blueprint
        blueprint = Blueprint(
            blueprint_id=blueprint_id,
            source_project_id=source_project_id,
            target_provider=target_provider,
            target_region=target_region,
            iac_engine=iac_engine,
            resources=blueprint_resources,
            created_at=time.time(),
            expires_at=time.time() + (24 * 3600),  # 24 hours
            download_token=download_token
        )
        
        # Generate files
        file_path = await BlueprintGenerator._generate_files(blueprint, include_docs)
        
        # Update file size
        if os.path.exists(file_path):
            blueprint.file_size_bytes = os.path.getsize(file_path)
        
        # Store in ephemeral vault (time-gated)
        BlueprintGenerator._store_blueprint_in_vault(blueprint, file_path)
        
        return blueprint
    
    @staticmethod
    def _generate_resource_blueprint(
        resource: Dict,
        source_provider: str,
        target_provider: str,
        target_region: str
    ) -> Optional[BlueprintResource]:
        """Generate blueprint for a single resource"""
        
        resource_type = resource['resource_type']
        
        # Map resource type
        mapped_type = BlueprintGenerator._map_resource_type(
            source_type=resource_type,
            source_provider=source_provider,
            target_provider=target_provider
        )
        
        # Get resource config
        config = json.loads(resource.get('configuration', '{}'))
        
        # Generate Terraform configuration
        tf_config = BlueprintGenerator._generate_terraform_config(
            resource_name=resource['resource_name'],
            resource_type=mapped_type,
            source_config=config,
            source_provider=source_provider,
            target_provider=target_provider,
            target_region=target_region
        )
        
        if not tf_config:
            return None
        
        # Determine complexity
        complexity = BlueprintGenerator._determine_complexity(
            source_type=resource_type,
            target_type=mapped_type,
            source_provider=source_provider,
            target_provider=target_provider
        )
        
        # Generate mapping notes
        mapping_notes = BlueprintGenerator._generate_mapping_notes(
            source_type=resource_type,
            target_type=mapped_type,
            source_provider=source_provider,
            target_provider=target_provider
        )
        
        return BlueprintResource(
            source_name=resource['resource_name'],
            source_type=resource_type,
            source_provider=source_provider,
            target_type=mapped_type,
            target_provider=target_provider,
            tf_config=tf_config,
            mapping_notes=mapping_notes,
            complexity=complexity
        )
    
    @staticmethod
    def _map_resource_type(
        source_type: str,
        source_provider: str,
        target_provider: str
    ) -> str:
        """Map resource type between cloud providers"""
        
        # Simple mapping table
        mapping_table = {
            "vm": {"aws": "vm", "gcp": "vm", "azure": "vm"},
            "database": {"aws": "database", "gcp": "database", "azure": "database"},
            "bucket": {"aws": "bucket", "gcp": "bucket", "azure": "bucket"},
            "vpc": {"aws": "vpc", "gcp": "vpc", "azure": "vpc"},
            "k8s": {"aws": "k8s", "gcp": "k8s", "azure": "k8s"}
        }
        
        # Default to same type if mapping not found
        return mapping_table.get(source_type, {}).get(target_provider, source_type)
    
    @staticmethod
    def _generate_terraform_config(
        resource_name: str,
        resource_type: str,
        source_config: Dict,
        source_provider: str,
        target_provider: str,
        target_region: str
    ) -> Dict:
        """Generate Terraform configuration for resource"""
        
        # Get template for this resource type
        template = BlueprintGenerator.RESOURCE_TEMPLATES.get(target_provider, {}).get(resource_type)
        if not template:
            return {}
        
        # Prepare variables for template
        timestamp = time.strftime("%Y-%m-%d")
        
        # Common variables
        variables = {
            "resource_name": resource_name,
            "source_provider": source_provider,
            "timestamp": timestamp,
            "location": target_region,
            "zone": target_region + "-a",  # Default zone
            "resource_group": "rg-" + resource_name[:20]  # Azure specific
        }
        
        # Add source config values if available
        if source_config:
            # Map common config keys
            config_mapping = {
                "machine_type": "instance_type",
                "disk_size_gb": "disk_size_gb",
                "instance_type": "machine_type"
            }
            
            for source_key, target_key in config_mapping.items():
                if source_key in source_config:
                    variables[target_key] = source_config[source_key]
        
        # Set defaults if not provided
        defaults = {
            "aws": {
                "ami_id": "ami-12345678",  # Example AMI
                "instance_type": "t3.micro",
                "instance_class": "db.t3.micro",
                "engine": "mysql",
                "storage_gb": 20
            },
            "gcp": {
                "machine_type": "e2-micro",
                "disk_size_gb": 20,
                "zone": target_region + "-a",
                "database_version": "MYSQL_8_0",
                "tier": "db-f1-micro"
            },
            "azure": {
                "vm_size": "Standard_B1s",
                "location": target_region,
                "resource_group": "migration-rg"
            }
        }
        
        # Apply defaults
        for key, value in defaults.get(target_provider, {}).items():
            if key not in variables:
                variables[key] = value
        
        # Format template with variables
        try:
            tf_code = template.format(**variables)
        except KeyError as e:
            # Missing variable, use placeholder
            tf_code = template.format(**{**variables, str(e).strip("'"): "PLACEHOLDER"})
        
        return {
            "tf_code": tf_code,
            "variables": variables,
            "resource_type": resource_type
        }
    
    @staticmethod
    def _determine_complexity(
        source_type: str,
        target_type: str,
        source_provider: str,
        target_provider: str
    ) -> str:
        """Determine migration complexity"""
        
        # Simple complexity rules
        if source_type != target_type:
            return "high"
        
        if source_provider != target_provider:
            if source_type in ["database", "k8s"]:
                return "high"
            elif source_type in ["vpc"]:
                return "medium"
            else:
                return "low"
        
        return "low"
    
    @staticmethod
    def _generate_mapping_notes(
        source_type: str,
        target_type: str,
        source_provider: str,
        target_provider: str
    ) -> List[str]:
        """Generate helpful mapping notes"""
        
        notes = []
        
        if source_type != target_type:
            notes.append(f"Resource type changed: {source_type} → {target_type}")
        
        if source_provider != target_provider:
            notes.append(f"Cloud provider changed: {source_provider.upper()} → {target_provider.upper()}")
        
        # Add provider-specific notes
        if target_provider == "aws":
            notes.append("AWS requires IAM permissions for resource creation")
        elif target_provider == "gcp":
            notes.append("GCP requires project and billing setup")
        elif target_provider == "azure":
            notes.append("Azure requires resource group creation first")
        
        # Add complexity-specific notes
        if source_type == "database":
            notes.append("Database migration requires data export/import")
        elif source_type == "k8s":
            notes.append("Kubernetes migration is complex - consider using specialized tools")
        
        return notes
    
    @staticmethod
    async def _generate_files(
        blueprint: Blueprint,
        include_docs: bool = True
    ) -> str:
        """Generate blueprint files on disk"""
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"blueprint_{blueprint.blueprint_id[:8]}_")
        
        try:
            # 1. Generate main Terraform file
            main_tf_path = os.path.join(temp_dir, "main.tf")
            with open(main_tf_path, 'w') as f:
                f.write("# Cloud Migration Blueprint - Generated by Discord Cloud Bot\n")
                f.write(f"# Source: {blueprint.source_project_id}\n")
                f.write(f"# Target: {blueprint.target_provider.upper()} ({blueprint.target_region})\n")
                f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("#\n" + "#" * 60 + "\n\n")
                
                # Provider configuration
                provider_config = BlueprintGenerator._generate_provider_config(
                    blueprint.target_provider,
                    blueprint.target_region
                )
                f.write(provider_config)
                f.write("\n\n")
                
                # Resource configurations
                for resource in blueprint.resources:
                    f.write(resource.tf_config['tf_code'])
                    f.write("\n\n")
            
            # 2. Generate variables file
            variables_tf_path = os.path.join(temp_dir, "variables.tf")
            with open(variables_tf_path, 'w') as f:
                f.write("""
variable "region" {
  description = "Cloud region"
  type        = string
  default     = "{region}"
}

variable "project_id" {
  description = "Cloud project ID"
  type        = string
  default     = "your-project-id"
}

variable "credentials_file" {
  description = "Path to cloud credentials file"
  type        = string
  default     = "~/.config/gcloud/application_default_credentials.json"
}
""".format(region=blueprint.target_region))
            
            # 3. Generate outputs file
            outputs_tf_path = os.path.join(temp_dir, "outputs.tf")
            with open(outputs_tf_path, 'w') as f:
                f.write("""
output "migration_summary" {
  description = "Migration blueprint summary"
  value = <<EOT
Migration Blueprint Generated Successfully

Source Project: {source_project_id}
Target Provider: {target_provider}
Target Region: {target_region}
Total Resources: {resource_count}

Next Steps:
1. Review the generated Terraform code
2. Update variables with your actual values
3. Run 'terraform init' and 'terraform plan'
4. Apply with 'terraform apply'

Note: This is a starting point - manual adjustments may be needed.
EOT
}
""".format(
    source_project_id=blueprint.source_project_id,
    target_provider=blueprint.target_provider.upper(),
    target_region=blueprint.target_region,
    resource_count=len(blueprint.resources)
))
            
            # 4. Generate README if requested
            if include_docs:
                readme_path = os.path.join(temp_dir, "README.md")
                with open(readme_path, 'w') as f:
                    f.write(BlueprintGenerator._generate_readme(blueprint))
            
            # 5. Generate mapping report
            report_path = os.path.join(temp_dir, "MAPPING_REPORT.md")
            with open(report_path, 'w') as f:
                f.write(BlueprintGenerator._generate_mapping_report(blueprint))
            
            # 6. Generate provider-specific config files
            provider_configs_path = os.path.join(temp_dir, "provider_configs")
            os.makedirs(provider_configs_path, exist_ok=True)
            
            # AWS specific
            if blueprint.target_provider == "aws":
                with open(os.path.join(provider_configs_path, "aws_backend.tf"), 'w') as f:
                    f.write("""
terraform {
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "migration/terraform.tfstate"
    region = "us-east-1"
  }
}
""")
            
            # GCP specific
            elif blueprint.target_provider == "gcp":
                with open(os.path.join(provider_configs_path, "gcp_backend.tf"), 'w') as f:
                    f.write("""
terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "migration"
  }
}
""")
            
            # Azure specific
            elif blueprint.target_provider == "azure":
                with open(os.path.join(provider_configs_path, "azure_backend.tf"), 'w') as f:
                    f.write("""
terraform {
  backend "azurerm" {
    resource_group_name  = "terraform-state"
    storage_account_name = "yourstorageaccount"
    container_name       = "terraform"
    key                  = "migration.terraform.tfstate"
  }
}
""")
            
            # 7. Create zip file
            zip_path = os.path.join(temp_dir, f"blueprint_{blueprint.blueprint_id[:8]}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.zip'):
                            continue  # Skip the zip file itself
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            return zip_path
            
        except Exception as e:
            # Cleanup on error
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e
    
    @staticmethod
    def _generate_provider_config(provider: str, region: str) -> str:
        """Generate provider configuration block"""
        
        configs = {
            "aws": f"""
provider "aws" {{
  region = "{region}"
  # Add your AWS credentials via environment variables or ~/.aws/credentials
}}
""",
            "gcp": f"""
provider "google" {{
  project = "${{var.project_id}}"
  region  = "{region}"
  # Credentials will be loaded from: ${{var.credentials_file}}
}}
""",
            "azure": f"""
provider "azurerm" {{
  features {{}}
  
  # Azure credentials can be set via environment variables:
  #   ARM_SUBSCRIPTION_ID
  #   ARM_TENANT_ID
  #   ARM_CLIENT_ID
  #   ARM_CLIENT_SECRET
}}
"""
        }
        
        return configs.get(provider, f"# Provider configuration for {provider} goes here")
    
    @staticmethod
    def _generate_readme(blueprint: Blueprint) -> str:
        """Generate comprehensive README"""
        
        return f"""# Cloud Migration Blueprint

## Overview
This blueprint contains Terraform code to migrate your infrastructure from your current environment to {blueprint.target_provider.upper()}.

## Generated Information
- **Blueprint ID**: `{blueprint.blueprint_id}`
- **Source Project**: `{blueprint.source_project_id}`
- **Target Provider**: {blueprint.target_provider.upper()}
- **Target Region**: {blueprint.target_region}
- **Generated At**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Total Resources**: {len(blueprint.resources)}
- **Expires At**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(blueprint.expires_at))}

## Files Included
1. `main.tf` - Main Terraform configuration
2. `variables.tf` - Input variables
3. `outputs.tf` - Output values
4. `README.md` - This file
5. `MAPPING_REPORT.md` - Detailed resource mapping

## Prerequisites
1. Install Terraform/OpenTofu
2. Set up {blueprint.target_provider.upper()} account
3. Configure cloud credentials
4. Review costs before applying

## Usage Steps
```bash
# 1. Extract this blueprint
unzip blueprint_{blueprint.blueprint_id[:8]}.zip
cd blueprint_{blueprint.blueprint_id[:8]}

# 2. Initialize Terraform
terraform init

# 3. Review the plan
terraform plan

# 4. Apply (if everything looks good)
terraform apply
```

## Important Notes
⚠️ **This is a blueprint, not a complete solution**
- Review all generated code
- Update variables with your actual values
- Test in a staging environment first
- Consider data migration separately
- Monitor costs closely

## Support
For questions about this blueprint, contact your Discord server administrator.

## Security
This blueprint expires 24 hours after generation. Download it again if needed.
"""
    
    @staticmethod
    def _generate_mapping_report(blueprint: Blueprint) -> str:
        """Generate detailed mapping report"""
        
        report = f"""# Resource Mapping Report

## Summary
- **Total Resources Mapped**: {len(blueprint.resources)}
- **Source Provider**: Various → **Target**: {blueprint.target_provider.upper()}
- **Complexity Distribution**: {sum(1 for r in blueprint.resources if r.complexity == 'high')} high, {sum(1 for r in blueprint.resources if r.complexity == 'medium')} medium, {sum(1 for r in blueprint.resources if r.complexity == 'low')} low

## Resource Details
"""
        
        for i, resource in enumerate(blueprint.resources, 1):
            report += f"""
### {i}. {resource.source_name}
- **Source Type**: {resource.source_type} ({resource.source_provider.upper()})
- **Target Type**: {resource.target_type} ({resource.target_provider.upper()})
- **Complexity**: {resource.complexity.upper()}

**Mapping Notes**:
"""
            for note in resource.mapping_notes:
                report += f"- {note}\n"
            
            if resource.complexity == "high":
                report += "\n⚠️ **High Complexity - Manual Steps Required**\n"
            elif resource.complexity == "medium":
                report += "\n⚠️ **Medium Complexity - Review Carefully**\n"
            
            report += "\n---\n"
        
        report += f"""
## Next Steps for Each Resource Type

### Virtual Machines (VMs)
- Review machine type mappings
- Check disk size requirements
- Update network configurations
- Plan for downtime during migration

### Databases
- **Data Migration Required**
- Export data from source
- Import to target
- Update connection strings in applications

### Storage Buckets
- Copy data between buckets
- Update ACLs and permissions
- Update application configurations

### VPC/Networking
- Review IP ranges and subnets
- Update firewall rules
- Recreate VPN connections if needed

### Kubernetes Clusters
- **Highly Complex Migration**
- Consider using specialized migration tools
- Test applications thoroughly
- Update ingress/load balancer configurations

## General Recommendations
- **Test First**: Create a test environment
- **Monitor Costs**: New cloud may have different pricing
- **Backup Everything**: Before any migration
- **Document Changes**: Keep track of all modifications
- **Plan Rollback**: Know how to revert if needed

## Provider-Specific Notes
"""
        
        if blueprint.target_provider == "aws":
            report += """
### AWS Specific
- IAM roles and permissions needed
- Security group rules must be reviewed
- Consider using AWS Migration Hub for large migrations
"""
        elif blueprint.target_provider == "gcp":
            report += """
### GCP Specific
- Project and billing setup required
- VPC networks differ from other clouds
- Consider Cloud Foundation Toolkit for best practices
"""
        elif blueprint.target_provider == "azure":
            report += """
### Azure Specific
- Resource groups must be created first
- Azure AD integration for permissions
- Consider Azure Migrate for assisted migration
"""
        
        report += f"""
---
Report generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Blueprint ID: {blueprint.blueprint_id}
"""
        
        return report
    
    @staticmethod
    def _store_blueprint_in_vault(blueprint: Blueprint, file_path: str):
        """Store blueprint in ephemeral vault (time-gated)"""
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Create vault data
        vault_data = {
            "blueprint_id": blueprint.blueprint_id,
            "source_project_id": blueprint.source_project_id,
            "target_provider": blueprint.target_provider,
            "target_region": blueprint.target_region,
            "created_at": blueprint.created_at,
            "expires_at": blueprint.expires_at,
            "download_token": blueprint.download_token,
            "file_size_bytes": len(file_content),
            "status": "available"
        }
        
        # Store in ephemeral vault
        ephemeral_vault.open_session(
            session_id=f"blueprint_{blueprint.blueprint_id}",
            raw_data=json.dumps(vault_data)
        )
        
        # Store file in temporary location with token as filename
        # This ensures only someone with the token can download
        temp_dir = "blueprint_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        
        token_file = os.path.join(temp_dir, f"{blueprint.download_token}.zip")
        with open(token_file, 'wb') as f:
            f.write(file_content)
        
        # Schedule cleanup
        BlueprintGenerator._schedule_cleanup(token_file, blueprint.expires_at)
    
    @staticmethod
    def _schedule_cleanup(file_path: str, expires_at: float):
        """Schedule file cleanup after expiration"""
        import threading
        
        def cleanup():
            delay = expires_at - time.time()
            if delay > 0:
                threading.Timer(delay, lambda: os.unlink(file_path) if os.path.exists(file_path) else None).start()
        
        # Run cleanup in background
        threading.Thread(target=cleanup, daemon=True).start()
    
    @staticmethod
    def get_blueprint_download(token: str) -> Optional[Tuple[str, Dict]]:
        """Get blueprint download by token (time-gated access)"""
        
        # Check if token file exists
        token_file = os.path.join("blueprint_downloads", f"{token}.zip")
        if not os.path.exists(token_file):
            return None
        
        # Check expiration via vault
        # Try to find the blueprint in vault by searching
        # Since we don't know the exact blueprint_id from token alone,
        # we'll store a reverse mapping or embed it in the token
        # For now, we'll search by checking all blueprint sessions
        vault_data = None
        
        # Get all active vault sessions and find matching token
        for session_id in list(ephemeral_vault._active_vaults.keys()):
            if session_id.startswith("blueprint_"):
                temp_data = ephemeral_vault.get_data(session_id)
                if temp_data:
                    try:
                        parsed_data = json.loads(temp_data)
                        if parsed_data.get('download_token') == token:
                            vault_data = temp_data
                            break
                    except:
                        continue
        
        if not vault_data:
            return None
        
        try:
            blueprint_data = json.loads(vault_data)
            
            # Check expiration
            if time.time() > blueprint_data.get('expires_at', 0):
                # Clean up expired file
                os.unlink(token_file)
                return None
            
            return token_file, blueprint_data
            
        except:
            return None
    
    @staticmethod
    def cleanup_expired_blueprints():
        """Clean up expired blueprints"""
        import shutil
        
        blueprint_dir = "blueprint_downloads"
        if not os.path.exists(blueprint_dir):
            return 0
        
        cleaned = 0
        current_time = time.time()
        
        for filename in os.listdir(blueprint_dir):
            if filename.endswith('.zip'):
                token = filename[:-4]  # Remove .zip
                
                # Check if associated vault session exists and is expired
                found_valid = False
                for session_id in list(ephemeral_vault._active_vaults.keys()):
                    if session_id.startswith("blueprint_"):
                        vault_data = ephemeral_vault.get_data(session_id)
                        if vault_data:
                            try:
                                blueprint_data = json.loads(vault_data)
                                if blueprint_data.get('download_token') == token:
                                    if current_time <= blueprint_data.get('expires_at', 0):
                                        found_valid = True
                                        break
                                    # Expired - will be cleaned
                            except:
                                continue
                
                # If no valid vault session found, clean up the file
                if not found_valid:
                    try:
                        os.unlink(os.path.join(blueprint_dir, filename))
                        cleaned += 1
                    except:
                        pass
        
        return cleaned


# Initialize cleanup on module import
import atexit
atexit.register(BlueprintGenerator.cleanup_expired_blueprints)
