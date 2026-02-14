# --- Cloud Provisioning Generator (SQL-Based) ---
"""
Cloud Infrastructure Generator - SQL Edition
Generates Terraform configurations from SQL database instead of Excel

Refactored from bot_newest/terraform to use proper database backend
"""

import os
import shutil
from typing import Dict, List, Optional
from collections import defaultdict
import cloud_database as cloud_db
import infrastructure_policy_validator as ipv


class CloudProvisioningGenerator:
    """Base class for cloud infrastructure generation"""
    
    def __init__(self, provider: str, project_id: str):
        self.provider = provider.lower()
        self.project_id = project_id
        self.output_dir = f'terraform_{self.provider}_{project_id}'
        self.hcl_store = defaultdict(list)
        self.errors = []
        self.warnings = []
        
        # Get project details
        self.project = cloud_db.get_cloud_project(project_id)
        if not self.project:
            raise ValueError(f"Project {project_id} not found")
        
        # File organization
        self.file_map = {
            'vm': 'compute.tf',
            'asg': 'compute.tf',
            'tmpl': 'compute.tf',
            'k8s': 'compute.tf',
            'serverless': 'compute.tf',
            'vpc': 'network.tf',
            'nat': 'network.tf',
            'lb': 'network.tf',
            'backend': 'network.tf',
            'firewall': 'security.tf',
            'waf': 'security.tf',
            'ssl': 'security.tf',
            'bucket': 'storage.tf',
            'db': 'storage.tf',
            'snapshot': 'storage.tf',
            'iam': 'iam.tf',
            'main': 'main.tf',
            'variables': 'variables.tf'
        }
    
    def add_hcl(self, category: str, hcl: str):
        """Add HCL code to specified category"""
        self.hcl_store[category].append(hcl.strip())
    
    def add_error(self, error: str):
        """Track generation error"""
        self.errors.append(error)
        print(f"❌ ERROR: {error}")
    
    def add_warning(self, warning: str):
        """Track generation warning"""
        self.warnings.append(warning)
        print(f"⚠️  WARNING: {warning}")
    
    def write_files(self) -> bool:
        """Write all HCL files to output directory"""
        try:
            print(f"📁 Generating {self.provider.upper()} files in {self.output_dir}...")
            
            if os.path.exists(self.output_dir):
                shutil.rmtree(self.output_dir)
            os.makedirs(self.output_dir)
            
            for category, blocks in self.hcl_store.items():
                filename = self.file_map.get(category, f"{category}.tf")
                path = os.path.join(self.output_dir, filename)
                
                with open(path, 'w') as f:
                    f.write("\n\n".join(blocks))
                    f.write("\n")
            
            print(f"✅ Generated {len(self.hcl_store)} Terraform files")
            
            if self.errors:
                print(f"⚠️  {len(self.errors)} errors encountered")
            if self.warnings:
                print(f"ℹ️  {len(self.warnings)} warnings")
            
            return len(self.errors) == 0
        
        except Exception as e:
            self.add_error(f"File generation failed: {e}")
            return False
    
    def safe_str(self, val, default=""):
        """Safely convert value to string"""
        if val is None or str(val).lower() in ['nan', 'none', '']:
            return default
        return str(val).strip()
    
    def clean_name(self, val: str) -> str:
        """Clean resource name for cloud provider"""
        clean = self.safe_str(val).replace(' ', '-').replace('_', '-').lower()
        return clean if clean else "unnamed"


class GCPGenerator(CloudProvisioningGenerator):
    """GCP-specific Terraform generator"""
    
    def __init__(self, project_id: str):
        super().__init__('gcp', project_id)
        self._init_provider()
    
    def _init_provider(self):
        """Initialize GCP provider configuration"""
        region = self.project.get('region', 'us-central1')
        
        self.add_hcl('main', f'''
terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = ">= 5.0"
    }}
  }}
}}

provider "google" {{
  project = "{self.project_id}"
  region  = "{region}"
}}
''')
        
        self.add_hcl('variables', f'''
variable "project_id" {{
  description = "GCP Project ID"
  default     = "{self.project_id}"
}}

variable "region" {{
  description = "Default region"
  default     = "{region}"
}}
''')
    
    def generate_vm(self, resource_config: Dict) -> bool:
        """Generate GCP Compute Engine instance"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-vm'))
            machine_type = self.safe_str(resource_config.get('machine_type'), 'e2-micro')
            zone = self.safe_str(resource_config.get('zone'), f"{self.project['region']}-a")
            disk_size = self.safe_str(resource_config.get('disk_size'), '20')
            disk_type = self.safe_str(resource_config.get('disk_type'), 'pd-standard')
            image = self.safe_str(resource_config.get('image'), 'debian-cloud/debian-11')
            network = self.safe_str(resource_config.get('network'), 'default')
            
            self.add_hcl('vm', f'''
resource "google_compute_instance" "{name}" {{
  name         = "{name}"
  machine_type = "{machine_type}"
  zone         = "{zone}"

  boot_disk {{
    initialize_params {{
      image = "{image}"
      size  = {disk_size}
      type  = "{disk_type}"
    }}
  }}

  network_interface {{
    network = "{network}"
    access_config {{
      // Ephemeral public IP
    }}
  }}

  tags = ["created-by-chatops", "project-{self.project_id}"]
  
  metadata = {{
    created-by = "chatops"
    project-id = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate VM {resource_config.get('name')}: {e}")
            return False
    
    def generate_database(self, resource_config: Dict) -> bool:
        """Generate GCP Cloud SQL instance"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-db'))
            tier = self.safe_str(resource_config.get('tier'), 'db-f1-micro')
            db_version = self.safe_str(resource_config.get('version'), 'POSTGRES_14')
            region = self.safe_str(resource_config.get('region'), self.project['region'])
            
            self.add_hcl('db', f'''
resource "google_sql_database_instance" "{name}" {{
  name             = "{name}"
  database_version = "{db_version}"
  region           = "{region}"

  settings {{
    tier = "{tier}"
    
    backup_configuration {{
      enabled = true
    }}
    
    ip_configuration {{
      ipv4_enabled = true
    }}
  }}

  deletion_protection = false
  
  labels = {{
    created-by = "chatops"
    project-id = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate database {resource_config.get('name')}: {e}")
            return False
    
    def generate_vpc(self, resource_config: Dict) -> bool:
        """Generate GCP VPC network"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-vpc'))
            subnet_cidr = self.safe_str(resource_config.get('subnet_cidr'), '10.0.0.0/24')
            region = self.safe_str(resource_config.get('region'), self.project['region'])
            
            self.add_hcl('vpc', f'''
resource "google_compute_network" "{name}" {{
  name                    = "{name}"
  auto_create_subnetworks = false
}}

resource "google_compute_subnetwork" "{name}_subnet" {{
  name          = "{name}-subnet"
  ip_cidr_range = "{subnet_cidr}"
  region        = "{region}"
  network       = google_compute_network.{name}.id
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate VPC {resource_config.get('name')}: {e}")
            return False
    
    def generate_bucket(self, resource_config: Dict) -> bool:
        """Generate GCP Storage Bucket"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-bucket'))
            location = self.safe_str(resource_config.get('location'), self.project['region']).upper()
            storage_class = self.safe_str(resource_config.get('storage_class'), 'STANDARD')
            
            self.add_hcl('bucket', f'''
resource "google_storage_bucket" "{name}" {{
  name          = "{self.project_id}-{name}"
  location      = "{location}"
  storage_class = "{storage_class}"
  
  uniform_bucket_level_access = true
  
  labels = {{
    created-by = "chatops"
    project-id = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate bucket {resource_config.get('name')}: {e}")
            return False


class AWSGenerator(CloudProvisioningGenerator):
    """AWS-specific Terraform generator"""
    
    def __init__(self, project_id: str):
        super().__init__('aws', project_id)
        self._init_provider()
    
    def _init_provider(self):
        """Initialize AWS provider configuration"""
        region = self.project.get('region', 'us-east-1')
        
        self.add_hcl('main', f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
  
  default_tags {{
    tags = {{
      CreatedBy = "chatops"
      ProjectId = "{self.project_id}"
    }}
  }}
}}
''')
        
        self.add_hcl('variables', f'''
variable "region" {{
  description = "AWS Region"
  default     = "{region}"
}}

variable "project_id" {{
  description = "Project ID"
  default     = "{self.project_id}"
}}
''')
    
    def generate_vm(self, resource_config: Dict) -> bool:
        """Generate AWS EC2 instance"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-vm'))
            instance_type = self.safe_str(resource_config.get('instance_type'), 't3.micro')
            ami = self.safe_str(resource_config.get('ami'), 'ami-0c55b159cbfafe1f0')  # Amazon Linux 2
            disk_size = self.safe_str(resource_config.get('disk_size'), '20')
            disk_type = self.safe_str(resource_config.get('disk_type'), 'gp3')
            
            self.add_hcl('vm', f'''
resource "aws_instance" "{name}" {{
  ami           = "{ami}"
  instance_type = "{instance_type}"
  
  root_block_device {{
    volume_size = {disk_size}
    volume_type = "{disk_type}"
  }}
  
  tags = {{
    Name      = "{name}"
    ProjectId = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate EC2 instance {resource_config.get('name')}: {e}")
            return False
    
    def generate_database(self, resource_config: Dict) -> bool:
        """Generate AWS RDS instance"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-db'))
            instance_class = self.safe_str(resource_config.get('instance_class'), 'db.t3.micro')
            engine = self.safe_str(resource_config.get('engine'), 'postgres')
            engine_version = self.safe_str(resource_config.get('engine_version'), '14')
            allocated_storage = self.safe_str(resource_config.get('allocated_storage'), '20')
            
            self.add_hcl('db', f'''
resource "aws_db_instance" "{name}" {{
  identifier        = "{name}"
  engine            = "{engine}"
  engine_version    = "{engine_version}"
  instance_class    = "{instance_class}"
  allocated_storage = {allocated_storage}
  
  username = "admin"
  password = "ChangeMe123!"  # Use AWS Secrets Manager in production
  
  skip_final_snapshot = true
  
  tags = {{
    Name      = "{name}"
    ProjectId = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate RDS instance {resource_config.get('name')}: {e}")
            return False
    
    def generate_vpc(self, resource_config: Dict) -> bool:
        """Generate AWS VPC"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-vpc'))
            cidr = self.safe_str(resource_config.get('cidr'), '10.0.0.0/16')
            
            self.add_hcl('vpc', f'''
resource "aws_vpc" "{name}" {{
  cidr_block = "{cidr}"
  
  tags = {{
    Name      = "{name}"
    ProjectId = "{self.project_id}"
  }}
}}

resource "aws_subnet" "{name}_subnet" {{
  vpc_id     = aws_vpc.{name}.id
  cidr_block = "{cidr}"
  
  tags = {{
    Name      = "{name}-subnet"
    ProjectId = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate VPC {resource_config.get('name')}: {e}")
            return False
    
    def generate_bucket(self, resource_config: Dict) -> bool:
        """Generate AWS S3 bucket"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-bucket'))
            
            self.add_hcl('bucket', f'''
resource "aws_s3_bucket" "{name}" {{
  bucket = "{self.project_id}-{name}"
  
  tags = {{
    Name      = "{name}"
    ProjectId = "{self.project_id}"
  }}
}}

resource "aws_s3_bucket_versioning" "{name}_versioning" {{
  bucket = aws_s3_bucket.{name}.id
  
  versioning_configuration {{
    status = "Enabled"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate S3 bucket {resource_config.get('name')}: {e}")
            return False


class AzureGenerator(CloudProvisioningGenerator):
    """Azure-specific Terraform generator"""
    
    def __init__(self, project_id: str):
        super().__init__('azure', project_id)
        self._init_provider()
    
    def _init_provider(self):
        """Initialize Azure provider configuration"""
        region = self.project.get('region', 'East US')
        
        self.add_hcl('main', f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}

resource "azurerm_resource_group" "main" {{
  name     = "{self.project_id}-rg"
  location = "{region}"
  
  tags = {{
    CreatedBy = "chatops"
    ProjectId = "{self.project_id}"
  }}
}}
''')
        
        self.add_hcl('variables', f'''
variable "location" {{
  description = "Azure Location"
  default     = "{region}"
}}

variable "project_id" {{
  description = "Project ID"
  default     = "{self.project_id}"
}}
''')
    
    def generate_vm(self, resource_config: Dict) -> bool:
        """Generate Azure Virtual Machine"""
        try:
            name = self.clean_name(resource_config.get('name', 'unnamed-vm'))
            vm_size = self.safe_str(resource_config.get('vm_size'), 'Standard_B1s')
            
            self.add_hcl('vm', f'''
resource "azurerm_virtual_machine" "{name}" {{
  name                  = "{name}"
  location              = azurerm_resource_group.main.location
  resource_group_name   = azurerm_resource_group.main.name
  vm_size               = "{vm_size}"
  
  tags = {{
    Name      = "{name}"
    ProjectId = "{self.project_id}"
  }}
}}
''')
            return True
        
        except Exception as e:
            self.add_error(f"Failed to generate Azure VM {resource_config.get('name')}: {e}")
            return False


# --- Helper Functions ---

def create_generator(provider: str, project_id: str) -> CloudProvisioningGenerator:
    """Factory function to create appropriate generator"""
    generators = {
        'gcp': GCPGenerator,
        'aws': AWSGenerator,
        'azure': AzureGenerator
    }
    
    generator_class = generators.get(provider.lower())
    if not generator_class:
        raise ValueError(f"Unsupported provider: {provider}")
    
    return generator_class(project_id)


def generate_infrastructure_from_session(session_id: str, user_id: str, guild_id: str) -> Dict:
    """
    Generate Terraform configuration from deployment session
    Includes validation before generation
    """
    # Get session
    session = cloud_db.get_deployment_session(session_id)
    
    if not session:
        return {
            'success': False,
            'error': 'Session not found or expired'
        }
    
    if session['status'] != 'approved':
        return {
            'success': False,
            'error': f'Session status is {session["status"]}, must be approved'
        }
    
    # Create generator
    try:
        generator = create_generator(session['provider'], session['project_id'])
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to create generator: {e}'
        }
    
    # Parse resources and generate
    resources = session.get('resources_pending', [])
    generated_count = 0
    
    for resource in resources:
        resource_type = resource.get('type')
        resource_config = resource.get('config', {})
        
        # Map resource type to generator method
        method_name = f"generate_{resource_type}"
        
        if hasattr(generator, method_name):
            success = getattr(generator, method_name)(resource_config)
            if success:
                generated_count += 1
        else:
            generator.add_warning(f"No generator method for {resource_type}")
    
    # Write files
    success = generator.write_files()
    
    # Update session
    if success:
        cloud_db.complete_deployment_session(session_id, 'completed')
    else:
        cloud_db.complete_deployment_session(session_id, 'failed')
    
    return {
        'success': success,
        'generated_count': generated_count,
        'total_resources': len(resources),
        'output_dir': generator.output_dir,
        'errors': generator.errors,
        'warnings': generator.warnings
    }
