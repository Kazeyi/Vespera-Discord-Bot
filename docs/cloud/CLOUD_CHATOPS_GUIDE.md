# Cloud Infrastructure ChatOps - Complete Documentation

## 🎯 Overview

The Cloud Infrastructure ChatOps system brings Discord-based infrastructure provisioning to your bot. It's inspired by your D&D combat system, using the same validation patterns for cloud deployments.

### Key Analogy: D&D → Cloud

| D&D System | Cloud ChatOps System |
|------------|----------------------|
| **ActionEconomyValidator** | **InfrastructurePolicyValidator** |
| Checks if player has 1 Action available | Checks if user can deploy db-n1-standard-1 in asia-southeast1 |
| Extra Attack feature (Fighter level 11 = 3 attacks) | Quota limits (Project has 10 VMs, 3 used = 7 available) |
| Character class permissions (Wizard can cast spells) | User role permissions (CloudAdmin can deploy K8s) |
| Combat session tracking | Ephemeral deployment sessions |
| Turn-based action economy | Resource quota management |

---

## 📋 Features Implemented

### ✅ Core Components

1. **cloud_database.py** - SQL database backend (replaces Excel)
   - Cloud projects management
   - Quota tracking and enforcement
   - User permissions (role-based)
   - Infrastructure policies
   - Ephemeral session management
   - Deployment history & audit logging

2. **infrastructure_policy_validator.py** - Policy validation engine
   - Permission checks (like D&D class abilities)
   - Quota validation (like Extra Attack limits)
   - Cost estimation
   - Policy compliance checking
   - Batch deployment validation

3. **cloud_provisioning_generator.py** - Terraform generators (SQL-based)
   - GCP Generator
   - AWS Generator
   - Azure Generator
   - Database-driven configuration
   - Error handling and validation

4. **cogs/cloud.py** - Discord ChatOps interface
   - `/cloud-init` - Create cloud projects
   - `/cloud-deploy` - Deploy infrastructure
   - `/cloud-list` - List deployed resources
   - `/cloud-quota` - Check quota usage
   - `/cloud-grant` - Manage permissions (admin)
   - `/cloud-projects` - List your projects
   - Interactive deployment lobby with approval workflow

5. **session_cleanup_service.py** - Memory leak prevention
   - Auto-expires deployment sessions
   - Cleans up old cache entries
   - Background cleanup task
   - Manual force cleanup option

6. **cloud_test_data.py** - Test data generator
   - Sample projects
   - User permissions
   - Infrastructure policies
   - Deployed resources
   - Validator testing

---

## 🚀 Quick Start Guide

### 1. Initialize the Database

```bash
cd /home/kazeyami/bot
python3 cloud_test_data.py
```

This will:
- Create the `cloud_infrastructure.db` database
- Generate sample projects, users, and policies
- Test the validator

### 2. Start the Bot

The Cloud cog is automatically loaded when you start your bot:

```bash
python3 main.py
```

### 3. Discord Commands

#### Create a Cloud Project

```
/cloud-init provider:gcp project_name:"Production API" region:us-central1
```

#### Deploy Infrastructure

```
/cloud-deploy project_id:gcp-abc123 resource_type:vm resource_name:web-server-01 machine_type:e2-medium
```

This opens an **interactive deployment lobby** with:
- ✅ Validation results
- 📊 Quota usage
- 💰 Cost estimate
- Approve/Cancel buttons

#### List Resources

```
/cloud-list project_id:gcp-abc123
```

#### Check Quotas

```
/cloud-quota project_id:gcp-abc123
```

#### Grant Permissions (Admin Only)

```
/cloud-grant user:@username provider:gcp role:user
```

---

## 🔐 Permission System

### Roles

**CloudViewer** (Read-only)
- View resources
- Check quotas
- No deployment permissions

**CloudUser** (Standard)
- Deploy VMs (up to medium size)
- Deploy databases
- Create networks & storage
- Cannot deploy K8s
- Cannot delete resources

**CloudAdmin** (Full Access)
- Deploy all resource types
- Create K8s clusters
- Delete and modify resources
- No size restrictions

### Granting Permissions

```python
# Example: Grant CloudUser role for GCP
cloud_db.grant_user_permission(
    user_id='123456789',
    guild_id='987654321',
    role_name='CloudUser',
    provider='gcp',
    can_create_vm=True,
    can_create_db=True,
    can_create_k8s=False,
    max_vm_size='medium',
    allowed_regions='us-central1,asia-southeast1',
    budget_limit=3000.0
)
```

---

## 📊 Quota Management

### How Quotas Work (Like D&D Extra Attack)

In D&D:
- Base: 1 attack per Attack action
- Fighter Level 5: Extra Attack → 2 attacks
- Fighter Level 11: Extra Attack (2) → 3 attacks

In Cloud ChatOps:
- Base: 10 VMs per project
- Used: 3 VMs
- Available: 7 VMs
- New deployment requesting 2 VMs → ✅ Allowed (7 available)

### Default Quotas Per Project

```python
{
    'compute.instances': 10,      # Max 10 VMs
    'compute.cpus': 24,            # Max 24 vCPUs
    'compute.ram_gb': 64,          # Max 64 GB RAM
    'database.instances': 5,       # Max 5 databases
    'storage.buckets': 20,         # Max 20 buckets
    'network.vpcs': 5,             # Max 5 VPCs
    'network.load_balancers': 5    # Max 5 load balancers
}
```

### Checking Quotas

```python
can_deploy, quota_info = cloud_db.check_quota(
    project_id='gcp-abc123',
    resource_type='compute.instances',
    region='us-central1',
    requested_amount=2
)

if can_deploy:
    print(f"✅ Can deploy! Available: {quota_info['available']}")
else:
    print(f"⛔ Quota exceeded: {quota_info['message']}")
```

---

## 🛡️ Infrastructure Policies

### Policy Types

1. **Permission** - Who can deploy what
2. **Quota** - Resource limits
3. **Region** - Geographic restrictions
4. **Cost** - Budget controls
5. **Security** - Security requirements

### Example Policies

```python
# Region restriction
cloud_db.create_policy(
    guild_id='123456789',
    policy_name='Production Regions Only',
    policy_type='region',
    resource_pattern='*',
    allowed_values='us-central1,us-east-1,eu-west-1',
    priority=10
)

# Cost limit
cloud_db.create_policy(
    guild_id='123456789',
    policy_name='Max $0.50/hour per VM',
    policy_type='cost',
    resource_pattern='type:compute.instances',
    max_cost_per_hour=0.50,
    require_approval=True,
    priority=50
)

# Security policy
cloud_db.create_policy(
    guild_id='123456789',
    policy_name='No Public Databases',
    policy_type='security',
    resource_pattern='type:database',
    denied_values='public,0.0.0.0/0',
    require_approval=True,
    priority=5
)
```

---

## 🔄 Ephemeral Session Management

### Why Ephemeral Sessions?

Prevents memory leaks by auto-expiring abandoned deployments.

**Without ephemeral sessions:**
- User starts deployment → Session created
- User forgets about it → Session stays forever
- Memory leak! 🐛

**With ephemeral sessions:**
- User starts deployment → Session created with 30-minute expiry
- Session auto-expires if not completed
- Memory freed! ✅

### Session Lifecycle

```
1. User runs /cloud-deploy
   ↓
2. Session created (expires_at = now + 30 minutes)
   ↓
3. User clicks "Approve & Deploy"
   ↓
4. Session marked as 'completed'
   OR
   30 minutes pass → Auto-expired by cleanup service
```

### Cleanup Service

Runs every 5 minutes to clean up:
- Expired deployment sessions
- Old policy cache entries
- Deployment history older than 90 days

```python
# Start cleanup service
await session_cleanup_service.start_cleanup_service()

# Force cleanup (manual)
result = session_cleanup_service.force_cleanup()

# Get stats
stats = session_cleanup_service.get_service_stats()
```

---

## 🧪 Validation Examples

### Example 1: Valid Deployment

```python
result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='111111111',
    guild_id='123456789',
    project_id='gcp-abc123',
    provider='gcp',
    resource_type='vm',
    resource_config={
        'name': 'web-server-01',
        'machine_type': 'e2-small',
        'region': 'us-central1'
    },
    region='us-central1'
)

# Result:
{
    'is_valid': True,
    'can_deploy': True,
    'violations': [],
    'quota_info': {
        'quota_available': True,
        'used': 3,
        'limit': 10,
        'available': 7
    },
    'cost_estimate': 0.0168,
    'warning': '✅ Validation passed - Ready to deploy'
}
```

### Example 2: Quota Exceeded

```python
# Project has 10/10 VMs already
result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='111111111',
    guild_id='123456789',
    project_id='gcp-abc123',
    provider='gcp',
    resource_type='vm',
    resource_config={'name': 'another-vm', 'machine_type': 'e2-micro'},
    region='us-central1'
)

# Result:
{
    'is_valid': False,
    'can_deploy': False,
    'violations': ['Quota limit exceeded'],
    'quota_info': {
        'quota_available': False,
        'used': 10,
        'limit': 10,
        'available': 0,
        'reason': 'Quota limit exceeded'
    },
    'warning': '⚠️ QUOTA EXCEEDED: Project has no available VM quota'
}
```

### Example 3: Permission Denied

```python
# User is CloudViewer (read-only)
result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='333333333',  # CloudViewer
    guild_id='123456789',
    project_id='gcp-abc123',
    provider='gcp',
    resource_type='vm',
    resource_config={'name': 'test-vm'},
    region='us-central1'
)

# Result:
{
    'is_valid': False,
    'can_deploy': False,
    'violations': ['User lacks can_create_vm permission'],
    'warning': '⛔ PERMISSION DENIED: User lacks can_create_vm permission'
}
```

---

## 🔧 Terraform Generation

### Workflow

1. User approves deployment in Discord
2. System generates Terraform configuration from SQL database
3. Files written to `terraform_<provider>_<project_id>/` directory
4. User runs `terraform apply` to deploy

### Example Generated Files

**GCP Example:**

```hcl
# terraform_gcp_abc123/compute.tf

resource "google_compute_instance" "web-server-01" {
  name         = "web-server-01"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 50
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  tags = ["created-by-chatops", "project-gcp-abc123"]
}
```

---

## 📈 Database Schema

### Key Tables

**cloud_projects**
- Stores cloud project metadata
- Links to quotas and resources

**cloud_quotas**
- Quota limits and usage tracking
- Per-resource-type limits

**user_cloud_permissions**
- Role-based permissions
- Machine size restrictions
- Region restrictions

**infrastructure_policies**
- Guild-wide policies
- Cost, security, region rules

**deployment_sessions** (Ephemeral)
- Temporary deployment tracking
- Auto-expires after timeout

**deployment_history**
- Audit log of all deployments
- Tracks status, errors, costs

**cloud_resources**
- Actual deployed resources
- Cost tracking
- Configuration storage

---

## 🎮 Comparison: D&D vs Cloud

### Action Economy Validator → Infrastructure Policy Validator

```python
# D&D: Validate player action
ActionEconomyValidator.validate_action_economy(
    action="I attack twice and cast fireball",
    character_data={'class': 'fighter', 'level': 11}
)
# Result: ⛔ Too many actions! Fighter can attack 3 times OR cast 1 spell

# Cloud: Validate deployment
InfrastructurePolicyValidator.validate_deployment(
    user_id='123',
    project_id='gcp-abc',
    resource_type='vm',
    resource_config={'machine_type': 'e2-xlarge'},
    region='us-central1'
)
# Result: ⛔ Machine type exceeds max allowed size (medium)
```

### Extra Attack → Quota Limits

```python
# D&D: Fighter with Extra Attack (2)
if attack_count <= extra_attacks:
    # ✅ Valid (2 attacks <= 2 allowed)
    
# Cloud: Project with VM quota
if vm_count <= vm_quota:
    # ✅ Valid (7 VMs <= 10 allowed)
```

### Character Class → User Role

```python
# D&D: Wizard can cast spells
if character_class == 'wizard':
    can_cast_spells = True

# Cloud: CloudAdmin can deploy K8s
if user_role == 'CloudAdmin':
    can_create_k8s = True
```

---

## 🧪 Testing

### Run Test Data Generator

```bash
cd /home/kazeyami/bot
python3 cloud_test_data.py
```

### Test Validator Directly

```python
import infrastructure_policy_validator as ipv

# Test deployment validation
result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='111111111',
    guild_id='123456789',
    project_id='gcp-test',
    provider='gcp',
    resource_type='vm',
    resource_config={'machine_type': 'e2-small'},
    region='us-central1'
)

print(result)
```

### Test Session Cleanup

```bash
python3 session_cleanup_service.py
```

---

## 🚨 Troubleshooting

### Database Not Found

```bash
# Initialize database
python3 -c "import cloud_database; cloud_database.init_cloud_database()"
```

### Permissions Not Working

```python
# Check user permissions
import cloud_database as cloud_db
perms = cloud_db.get_user_permissions('USER_ID', 'GUILD_ID', 'gcp')
print(perms)
```

### Sessions Not Expiring

```python
# Force cleanup
import session_cleanup_service as scs
result = scs.force_cleanup()
print(result)
```

---

## 📚 API Reference

### cloud_database.py

```python
# Projects
create_cloud_project(guild_id, owner_user_id, provider, project_name, region, budget_limit)
get_cloud_project(project_id)
list_user_projects(user_id, guild_id)

# Quotas
check_quota(project_id, resource_type, region, requested_amount)
consume_quota(project_id, resource_type, region, amount)
release_quota(project_id, resource_type, region, amount)

# Permissions
get_user_permissions(user_id, guild_id, provider)
grant_user_permission(user_id, guild_id, role_name, provider, **permissions)

# Sessions
create_deployment_session(project_id, user_id, guild_id, channel_id, provider, deployment_type, resources, timeout_minutes)
get_deployment_session(session_id)
cleanup_expired_sessions()
complete_deployment_session(session_id, status)

# Policies
create_policy(guild_id, policy_name, policy_type, resource_pattern, **kwargs)
get_guild_policies(guild_id, is_active)

# Resources
create_cloud_resource(project_id, provider, resource_type, resource_name, region, config, created_by, **kwargs)
get_project_resources(project_id, resource_type)
```

### infrastructure_policy_validator.py

```python
InfrastructurePolicyValidator.validate_deployment(user_id, guild_id, project_id, provider, resource_type, resource_config, region)
InfrastructurePolicyValidator.validate_batch_deployment(user_id, guild_id, project_id, provider, resources)
```

### cloud_provisioning_generator.py

```python
create_generator(provider, project_id)
generate_infrastructure_from_session(session_id, user_id, guild_id)

# Generators
GCPGenerator(project_id).generate_vm(resource_config)
GCPGenerator(project_id).generate_database(resource_config)
AWSGenerator(project_id).generate_vm(resource_config)
AzureGenerator(project_id).generate_vm(resource_config)
```

---

## ✅ What's Complete

1. ✅ SQL database backend (no more Excel!)
2. ✅ InfrastructurePolicyValidator (like ActionEconomyValidator)
3. ✅ Ephemeral session management (prevents memory leaks)
4. ✅ Quota system (like Extra Attack logic)
5. ✅ Permission system (like D&D class abilities)
6. ✅ Policy engine (guild-wide rules)
7. ✅ Terraform generators (GCP, AWS, Azure)
8. ✅ Discord ChatOps cog with interactive lobby
9. ✅ Session cleanup service
10. ✅ Test data generator
11. ✅ Cost estimation
12. ✅ Audit logging

---

## 🎯 Next Steps

1. **Test in Discord**: Run the bot and try `/cloud-init`
2. **Customize Policies**: Add your own infrastructure policies
3. **Grant Permissions**: Set up user roles for your team
4. **Deploy Infrastructure**: Use the deployment lobby to generate Terraform
5. **Monitor Quotas**: Track resource usage and costs

---

## 💡 Pro Tips

1. **Use Ephemeral Sessions**: Sessions auto-expire to prevent clutter
2. **Set Budget Limits**: Control costs at the project level
3. **Create Policies First**: Set up policies before granting permissions
4. **Test with Test Data**: Use `cloud_test_data.py` to explore features
5. **Monitor Cleanup Service**: Check stats with `get_service_stats()`

---

## 🤝 Support

Created by: GitHub Copilot (Claude Sonnet 4.5)
Date: January 29, 2026

For issues or questions, check the implementation files:
- [cloud_database.py](cloud_database.py)
- [infrastructure_policy_validator.py](infrastructure_policy_validator.py)
- [cloud_provisioning_generator.py](cloud_provisioning_generator.py)
- [cogs/cloud.py](cogs/cloud.py)
- [session_cleanup_service.py](session_cleanup_service.py)
- [cloud_test_data.py](cloud_test_data.py)

**Happy provisioning! ☁️🚀**
