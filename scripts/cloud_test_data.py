# --- Cloud Infrastructure Test Data Generator ---
"""
Generate test data for ChatOps cloud infrastructure system
Creates sample projects, quotas, permissions, and policies
"""

import cloud_database as cloud_db
import infrastructure_policy_validator as ipv


def create_test_projects(guild_id: str = "123456789"):
    """Create sample cloud projects"""
    print("📦 Creating test cloud projects...")
    
    projects = [
        {
            'owner_user_id': '111111111',
            'provider': 'gcp',
            'project_name': 'Production API',
            'region': 'us-central1',
            'budget_limit': 5000.0
        },
        {
            'owner_user_id': '111111111',
            'provider': 'aws',
            'project_name': 'Dev Environment',
            'region': 'us-east-1',
            'budget_limit': 1000.0
        },
        {
            'owner_user_id': '222222222',
            'provider': 'azure',
            'project_name': 'ML Training',
            'region': 'East US',
            'budget_limit': 3000.0
        },
        {
            'owner_user_id': '111111111',
            'provider': 'gcp',
            'project_name': 'Staging',
            'region': 'asia-southeast1',
            'budget_limit': 2000.0
        }
    ]
    
    created_projects = []
    
    for project_data in projects:
        try:
            project_id = cloud_db.create_cloud_project(
                guild_id=guild_id,
                **project_data
            )
            created_projects.append(project_id)
            print(f"✅ Created project: {project_id} ({project_data['project_name']})")
        except Exception as e:
            print(f"❌ Failed to create project {project_data['project_name']}: {e}")
    
    return created_projects


def create_test_permissions(guild_id: str = "123456789"):
    """Create sample user permissions"""
    print("\n🔐 Creating test user permissions...")
    
    permissions = [
        {
            'user_id': '111111111',
            'role_name': 'CloudAdmin',
            'provider': 'all',
            'can_create_vm': True,
            'can_create_db': True,
            'can_create_k8s': True,
            'can_create_network': True,
            'can_create_storage': True,
            'can_delete': True,
            'can_modify': True,
            'allowed_regions': 'us-central1,us-east-1,asia-southeast1',
            'budget_limit': 10000.0
        },
        {
            'user_id': '222222222',
            'role_name': 'CloudUser',
            'provider': 'gcp',
            'can_create_vm': True,
            'can_create_db': True,
            'can_create_k8s': False,
            'can_create_network': True,
            'can_create_storage': True,
            'can_delete': False,
            'can_modify': True,
            'max_vm_size': 'medium',
            'max_db_size': 'db-n1-standard-2',
            'allowed_regions': 'us-central1,asia-southeast1',
            'budget_limit': 3000.0
        },
        {
            'user_id': '333333333',
            'role_name': 'CloudViewer',
            'provider': 'all',
            'can_create_vm': False,
            'can_create_db': False,
            'can_create_k8s': False,
            'can_create_network': False,
            'can_create_storage': False,
            'can_delete': False,
            'can_modify': False
        }
    ]
    
    for perm_data in permissions:
        try:
            cloud_db.grant_user_permission(
                guild_id=guild_id,
                **perm_data
            )
            print(f"✅ Granted {perm_data['role_name']} to user {perm_data['user_id']}")
        except Exception as e:
            print(f"❌ Failed to grant permission: {e}")


def create_test_policies(guild_id: str = "123456789"):
    """Create sample infrastructure policies"""
    print("\n📋 Creating test infrastructure policies...")
    
    policies = [
        {
            'policy_name': 'Region Restriction - Production',
            'policy_type': 'region',
            'resource_pattern': '*',
            'allowed_values': 'us-central1,us-east-1,eu-west-1',
            'max_instances': None,
            'max_cost_per_hour': None,
            'require_approval': False,
            'priority': 10
        },
        {
            'policy_name': 'Cost Limit - Standard VMs',
            'policy_type': 'cost',
            'resource_pattern': 'type:compute.instances',
            'max_cost_per_hour': 0.50,
            'require_approval': True,
            'priority': 50
        },
        {
            'policy_name': 'Security - No Public Databases',
            'policy_type': 'security',
            'resource_pattern': 'type:database',
            'denied_values': 'public,0.0.0.0/0',
            'require_approval': True,
            'priority': 5
        },
        {
            'policy_name': 'Quota - Max 10 VMs per Project',
            'policy_type': 'quota',
            'resource_pattern': 'type:compute.instances',
            'max_instances': 10,
            'require_approval': False,
            'priority': 20
        },
        {
            'policy_name': 'Cost Alert - High Usage',
            'policy_type': 'cost',
            'resource_pattern': '*',
            'max_cost_per_hour': 5.0,
            'require_approval': True,
            'priority': 100
        }
    ]
    
    for policy_data in policies:
        try:
            policy_id = cloud_db.create_policy(
                guild_id=guild_id,
                **policy_data
            )
            print(f"✅ Created policy #{policy_id}: {policy_data['policy_name']}")
        except Exception as e:
            print(f"❌ Failed to create policy {policy_data['policy_name']}: {e}")


def create_test_resources(project_id: str):
    """Create sample deployed resources"""
    print(f"\n📦 Creating test resources for project {project_id}...")
    
    resources = [
        {
            'provider': 'gcp',
            'resource_type': 'compute.instances',
            'resource_name': 'web-server-01',
            'region': 'us-central1',
            'config': {
                'machine_type': 'e2-medium',
                'disk_size': 50,
                'zone': 'us-central1-a'
            },
            'cost_per_hour': 0.0336,
            'created_by': '111111111',
            'zone': 'us-central1-a'
        },
        {
            'provider': 'gcp',
            'resource_type': 'database.instances',
            'resource_name': 'postgres-main',
            'region': 'us-central1',
            'config': {
                'tier': 'db-n1-standard-1',
                'version': 'POSTGRES_14'
            },
            'cost_per_hour': 0.095,
            'created_by': '111111111'
        },
        {
            'provider': 'gcp',
            'resource_type': 'storage.buckets',
            'resource_name': 'app-uploads',
            'region': 'us-central1',
            'config': {
                'storage_class': 'STANDARD'
            },
            'cost_per_hour': 0.001,
            'created_by': '111111111'
        }
    ]
    
    for resource_data in resources:
        try:
            resource_id = cloud_db.create_cloud_resource(
                project_id=project_id,
                **resource_data
            )
            
            # Update quota
            cloud_db.consume_quota(
                project_id,
                resource_data['resource_type'],
                resource_data['region'],
                1
            )
            
            print(f"✅ Created resource: {resource_id} ({resource_data['resource_name']})")
        except Exception as e:
            print(f"❌ Failed to create resource {resource_data['resource_name']}: {e}")


def test_validator():
    """Test InfrastructurePolicyValidator"""
    print("\n🧪 Testing InfrastructurePolicyValidator...")
    
    # Test case 1: Valid deployment
    print("\n--- Test 1: Valid VM Deployment ---")
    result = ipv.InfrastructurePolicyValidator.validate_deployment(
        user_id='111111111',
        guild_id='123456789',
        project_id='gcp-test123',
        provider='gcp',
        resource_type='vm',
        resource_config={
            'name': 'test-vm',
            'machine_type': 'e2-small',
            'region': 'us-central1'
        },
        region='us-central1'
    )
    
    print(f"✅ Valid: {result['is_valid']}")
    print(f"   Can Deploy: {result['can_deploy']}")
    print(f"   Cost Estimate: ${result.get('cost_estimate', 0):.4f}/hour")
    print(f"   Warning: {result.get('warning', 'None')}")
    
    # Test case 2: Quota exceeded
    print("\n--- Test 2: Database with Region Check ---")
    result2 = ipv.InfrastructurePolicyValidator.validate_deployment(
        user_id='222222222',
        guild_id='123456789',
        project_id='gcp-test456',
        provider='gcp',
        resource_type='database',
        resource_config={
            'name': 'test-db',
            'tier': 'db-n1-standard-1',
            'region': 'asia-southeast1'
        },
        region='asia-southeast1'
    )
    
    print(f"✅ Valid: {result2['is_valid']}")
    print(f"   Can Deploy: {result2['can_deploy']}")
    print(f"   Cost Estimate: ${result2.get('cost_estimate', 0):.4f}/hour")
    if result2.get('violations'):
        print(f"   Violations: {', '.join(result2['violations'])}")


def generate_all_test_data():
    """Generate all test data"""
    print("=" * 60)
    print("🚀 Cloud Infrastructure ChatOps - Test Data Generator")
    print("=" * 60)
    
    # Initialize database
    cloud_db.init_cloud_database()
    
    # Create test data
    guild_id = "123456789"
    
    projects = create_test_projects(guild_id)
    create_test_permissions(guild_id)
    create_test_policies(guild_id)
    
    # Add resources to first project
    if projects:
        create_test_resources(projects[0])
    
    # Test validator
    test_validator()
    
    print("\n" + "=" * 60)
    print("✅ Test data generation complete!")
    print("=" * 60)
    print(f"\nCreated:")
    print(f"  • {len(projects)} cloud projects")
    print(f"  • 3 user permission sets")
    print(f"  • 5 infrastructure policies")
    print(f"  • 3 sample resources")
    print("\nTest Users:")
    print("  • 111111111 - CloudAdmin (full access)")
    print("  • 222222222 - CloudUser (limited access)")
    print("  • 333333333 - CloudViewer (read-only)")
    print("\nYou can now test the ChatOps commands in Discord!")


if __name__ == "__main__":
    generate_all_test_data()
