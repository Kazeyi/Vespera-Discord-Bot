# ☁️ Cloud ChatOps - Quick Reference Card

## 🎯 D&D → Cloud Analogy

| D&D Component | Cloud Component |
|---------------|-----------------|
| ActionEconomyValidator | InfrastructurePolicyValidator |
| 1 Action per turn | Quota limits (10 VMs max) |
| Extra Attack (Fighter) | Quota overrides |
| Character class abilities | User role permissions |
| Combat session | Deployment session (ephemeral) |
| Turn counter | Session timeout (30 min) |

## 📂 Files Created

```
/home/kazeyami/bot/
├── cloud_database.py                    # SQL database backend
├── infrastructure_policy_validator.py   # Policy & quota validator
├── cloud_provisioning_generator.py      # Terraform generators
├── session_cleanup_service.py           # Memory leak prevention
├── cloud_test_data.py                   # Test data generator
├── CLOUD_CHATOPS_GUIDE.md              # Complete documentation
├── CLOUD_CHATOPS_QUICKREF.md           # This file
└── cogs/
    └── cloud.py                         # Discord commands
```

## 💬 Discord Commands

```bash
# Initialize project
/cloud-init provider:gcp project_name:"My Project" region:us-central1

# List your projects
/cloud-projects

# Deploy infrastructure
/cloud-deploy project_id:gcp-abc123 resource_type:vm resource_name:web-server machine_type:e2-medium

# List resources
/cloud-list project_id:gcp-abc123

# Check quotas
/cloud-quota project_id:gcp-abc123

# Grant permissions (admin only)
/cloud-grant user:@username provider:gcp role:user
```

## 🔐 User Roles

**CloudViewer** - Read-only access
**CloudUser** - Deploy VMs, DBs, storage (limited)
**CloudAdmin** - Full access including K8s

## 🚀 Quick Start (3 Steps)

```bash
# 1. Generate test data
cd /home/kazeyami/bot
python3 cloud_test_data.py

# 2. Start bot
python3 main.py

# 3. Test in Discord
/cloud-init provider:gcp project_name:"Test" region:us-central1
```

## 🧪 Test Users (from cloud_test_data.py)

- `111111111` - CloudAdmin (full access)
- `222222222` - CloudUser (limited)
- `333333333` - CloudViewer (read-only)

## 📊 Default Quotas

```python
{
    'compute.instances': 10,
    'compute.cpus': 24,
    'compute.ram_gb': 64,
    'database.instances': 5,
    'storage.buckets': 20,
    'network.vpcs': 5,
    'network.load_balancers': 5
}
```

## 🛡️ Policy Types

1. **permission** - Who can deploy what
2. **quota** - Resource limits
3. **region** - Geographic restrictions
4. **cost** - Budget controls
5. **security** - Security requirements

## 🔄 Session Lifecycle

```
User runs /cloud-deploy
    ↓
Session created (30 min TTL)
    ↓
Validation runs
    ↓
User approves → Terraform generated
    OR
30 minutes → Auto-expired
```

## 💰 Cost Estimates

```python
GCP:
  e2-micro:        $0.0084/hr  (~$6/mo)
  e2-small:        $0.0168/hr  (~$12/mo)
  e2-medium:       $0.0336/hr  (~$24/mo)
  db-n1-standard-1: $0.095/hr  (~$68/mo)

AWS:
  t3.micro:        $0.0104/hr  (~$7.50/mo)
  t3.small:        $0.0208/hr  (~$15/mo)
  db.t3.micro:     $0.017/hr   (~$12/mo)
```

## 🧹 Cleanup Service

```python
# Auto-runs every 5 minutes
# Cleans:
- Expired sessions
- Old cache entries
- History > 90 days

# Manual cleanup
import session_cleanup_service as scs
scs.force_cleanup()
```

## 🧪 Validation Example

```python
import infrastructure_policy_validator as ipv

result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='111111111',
    guild_id='123456789',
    project_id='gcp-abc',
    provider='gcp',
    resource_type='vm',
    resource_config={'machine_type': 'e2-small'},
    region='us-central1'
)

print(result['is_valid'])      # True/False
print(result['can_deploy'])    # True/False
print(result['cost_estimate']) # $0.0168
```

## 🎮 Interactive Deployment Lobby

When you run `/cloud-deploy`, you get:

```
☁️ Cloud Infrastructure Deployment Lobby

✅ Validation Passed
   Ready to deploy

📦 Resource
   Type: Virtual Machine (VM)
   Name: web-server-01

📊 Quota
   3/10 used (7 available)

💰 Estimated Cost
   $0.0336/hour (~$24.19/month)

⏱️ Session
   ID: deploy-abc123def456
   Expires in 30 minutes

[✅ Approve & Deploy] [❌ Cancel] [📊 View Details]
```

## 🔧 Direct Python Usage

```python
import cloud_database as cloud_db
import infrastructure_policy_validator as ipv
import cloud_provisioning_generator as cpg

# Create project
project_id = cloud_db.create_cloud_project(
    guild_id='123',
    owner_user_id='456',
    provider='gcp',
    project_name='Test',
    region='us-central1'
)

# Check quota
can_deploy, info = cloud_db.check_quota(
    project_id, 'compute.instances', 'us-central1', 1
)

# Validate deployment
result = ipv.InfrastructurePolicyValidator.validate_deployment(
    user_id='456',
    guild_id='123',
    project_id=project_id,
    provider='gcp',
    resource_type='vm',
    resource_config={'machine_type': 'e2-micro'},
    region='us-central1'
)

# Generate Terraform
generator = cpg.GCPGenerator(project_id)
generator.generate_vm({'name': 'test', 'machine_type': 'e2-micro'})
generator.write_files()
```

## 🚨 Common Issues

### Database not initialized
```bash
python3 -c "import cloud_database; cloud_database.init_cloud_database()"
```

### No permissions
```python
import cloud_database as cloud_db
cloud_db.grant_user_permission(
    user_id='YOUR_ID',
    guild_id='GUILD_ID',
    role_name='CloudAdmin',
    provider='all',
    can_create_vm=True,
    can_create_db=True,
    can_create_k8s=True
)
```

### Sessions stuck
```python
import session_cleanup_service as scs
scs.force_cleanup()
```

## 📈 Database Schema (Key Tables)

- `cloud_projects` - Project metadata
- `cloud_quotas` - Quota tracking
- `user_cloud_permissions` - User permissions
- `infrastructure_policies` - Guild policies
- `deployment_sessions` - Ephemeral sessions
- `deployment_history` - Audit log
- `cloud_resources` - Deployed resources

## ✅ Feature Checklist

- [x] SQL database (no Excel)
- [x] InfrastructurePolicyValidator
- [x] Ephemeral sessions
- [x] Quota management
- [x] Permission system
- [x] Policy engine
- [x] GCP/AWS/Azure generators
- [x] Discord ChatOps cog
- [x] Session cleanup service
- [x] Cost estimation
- [x] Audit logging
- [x] Test data generator

## 🎯 Key Innovation

**Ephemeral Sessions** prevent memory leaks:
- Auto-expire after 30 minutes
- Background cleanup every 5 minutes
- No manual cleanup needed
- Project IDs freed automatically

This is similar to how your D&D combat sessions work, but with automatic cleanup to prevent abandoned deployments from consuming memory!

---

**Created by**: GitHub Copilot (Claude Sonnet 4.5)  
**Date**: January 29, 2026  
**See**: [CLOUD_CHATOPS_GUIDE.md](CLOUD_CHATOPS_GUIDE.md) for full documentation
