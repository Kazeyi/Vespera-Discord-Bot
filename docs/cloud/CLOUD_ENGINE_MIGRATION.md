# Cloud Engine v2.0 - Migration Guide

## Overview

This guide helps you migrate from the monolithic `cogs/cloud.py` to the new modular `cloud_engine/` architecture.

## What Changed?

### Before (v1.0)
```
cogs/cloud.py (561 lines) - Everything in one file
├── DeploymentLobbyView
├── CloudCommands cog
├── Direct database calls
└── No plan preview
```

### After (v2.0)
```
cloud_engine/
├── models/session.py - State objects (CloudSession, PlanResult)
├── core/orchestrator.py - Business logic layer
├── core/terraform_runner.py - Async terraform execution
├── ui/lobby_view.py - Refactored UI components
├── cogs/user_commands.py - User-facing commands
└── cogs/admin_commands.py - Admin commands
```

## Migration Steps

### Step 1: Update main.py

**Before:**
```python
# Old way
await bot.load_extension('cogs.cloud')
```

**After:**
```python
# New way - load both command modules
await bot.load_extension('cloud_engine.cogs.user_commands')
await bot.load_extension('cloud_engine.cogs.admin_commands')
```

### Step 2: Test the New Commands

The command names are mostly the same:

| Old Command | New Command | Changes |
|------------|-------------|---------|
| `/cloud-deploy` | `/cloud-deploy` | ✅ Now runs terraform plan automatically |
| `/cloud-list` | `/cloud-list` | ✅ Same functionality |
| `/cloud-quota` | `/cloud-quota` | ✅ Same functionality |
| `/cloud-grant` | `/cloud-grant` | ✅ Same functionality |
| `/cloud-approve` | Removed | ⚠️ Approval now happens in lobby view |

### Step 3: Update Database Calls (If You Have Custom Code)

**Before:**
```python
from cloud_database import CloudDatabase

db = CloudDatabase()
db.create_deployment_session(project_id, user_id)
```

**After:**
```python
from cloud_engine import CloudOrchestrator
from cloud_database import CloudDatabase

db = CloudDatabase()
orchestrator = CloudOrchestrator(db)

# Use orchestrator instead of direct database calls
session = await orchestrator.start_session(
    user_id=user_id,
    project_id=project_id,
    provider='gcp'
)
```

### Step 4: Remove Old cloud.py (Optional)

Once you've verified everything works:

```bash
# Backup the old file first
mv cogs/cloud.py cogs/cloud.py.backup

# Or delete it
rm cogs/cloud.py
```

## Key Improvements

### 1. Plan-First Workflow

**Old Behavior:**
1. User clicks "Approve & Deploy"
2. Generates terraform files
3. Runs `terraform apply` immediately
4. No preview of what will change

**New Behavior:**
1. User clicks `/cloud-deploy`
2. Lobby appears with "Planning..." message
3. Runs `terraform plan` automatically
4. Shows: "Plan: 2 to add, 0 to change, 0 to destroy"
5. "Approve & Deploy" button becomes enabled
6. User reviews plan, then approves
7. Runs `terraform apply` with pre-generated plan

### 2. Discord Threads for Output

**Old Behavior:**
- Terraform output sent as single message
- Hard to read long outputs
- Clutters main channel

**New Behavior:**
- Creates Discord thread automatically
- Streams output line-by-line
- Real-time progress updates
- Keeps main channel clean

### 3. Separation of Concerns

**Old Architecture:**
```
Discord Command → Database → Done
(Everything mixed together)
```

**New Architecture:**
```
Discord Command (UI)
    ↓
CloudOrchestrator (Business Logic)
    ↓
Database + Validator + TerraformRunner
(Clean separation)
```

### 4. State-Based Session Management

**Old Approach:**
- Sessions stored as dicts
- State tracked with strings
- Hard to validate state transitions

**New Approach:**
- CloudSession dataclass with properties
- DeploymentState enum (DRAFT → PLANNING → PLAN_READY → APPROVED → APPLYING → APPLIED)
- Built-in validation (can't approve until plan succeeds)

## Example: Creating a Custom Workflow

With v2.0, you can easily build custom workflows:

```python
from cloud_engine import CloudOrchestrator, DeploymentState
from cloud_database import CloudDatabase

# Initialize
db = CloudDatabase()
orchestrator = CloudOrchestrator(db)

# Start session
session = await orchestrator.start_session(
    user_id=123456789,
    project_id='my-project',
    provider='gcp'
)

# Add resources
orchestrator.add_resource(
    session.id,
    'compute_vm',
    {
        'name': 'web-server-01',
        'machine_type': 'e2-medium',
        'region': 'us-central1'
    }
)

# Validate
validation = await orchestrator.validate_session(session.id)

if validation['is_valid']:
    # Run plan
    plan_result = await orchestrator.run_plan(session.id)
    
    if plan_result.success:
        print(f"Plan will create {plan_result.resources_to_add} resources")
        
        # Approve and apply
        await orchestrator.approve_and_apply(session.id, approver_id=123456789)
```

## Troubleshooting

### Issue: Commands not showing up

**Solution:** Make sure you sync commands:
```python
await bot.tree.sync()
```

### Issue: "Module not found: cloud_engine"

**Solution:** Ensure cloud_engine/ directory is in the same folder as your main.py:
```
bot/
├── main.py
├── cloud_engine/
│   ├── __init__.py
│   ├── models/
│   ├── core/
│   ├── ui/
│   └── cogs/
└── cloud_database.py
```

### Issue: Import errors in orchestrator.py

**Solution:** The orchestrator imports from the old modules. Ensure these exist:
- `cloud_database.py`
- `infrastructure_policy_validator.py`
- `cloud_provisioning_generator.py`

### Issue: Terraform not found

**Solution:** Install terraform:
```bash
# Ubuntu/Debian
sudo apt-get install terraform

# MacOS
brew install terraform

# Windows
choco install terraform
```

## Rollback Plan

If you need to rollback to v1.0:

```bash
# Restore old cloud.py
mv cogs/cloud.py.backup cogs/cloud.py

# Update main.py
# Change from:
await bot.load_extension('cloud_engine.cogs.user_commands')
await bot.load_extension('cloud_engine.cogs.admin_commands')

# Back to:
await bot.load_extension('cogs.cloud')
```

## Next Steps

1. ✅ Load the new cogs in main.py
2. ✅ Test `/cloud-deploy` command
3. ✅ Verify plan-first workflow works
4. ✅ Test thread creation for apply output
5. ✅ Grant permissions to test users
6. ✅ Create a test project
7. ✅ Deploy test infrastructure

## Support

If you encounter issues:
1. Check the logs for error messages
2. Verify terraform is installed
3. Ensure database exists (cloud_infrastructure.db)
4. Test with a simple deployment first

## Additional Features in v2.0

### Admin Commands

New admin-only commands:
- `/cloud-admin-list` - View all deployments
- `/cloud-admin-cancel` - Cancel any deployment
- `/cloud-stats` - View deployment statistics

### JIT Access Control

Admins can grant temporary access:
```
/cloud-grant @user my-project deploy
```

This implements Just-In-Time access for better security.

### Cost Estimation

Plan results now include estimated costs:
- Hourly cost estimate
- Monthly cost projection
- Per-resource breakdown (coming soon)

### Progress Tracking

New state lifecycle with clear transitions:
```
DRAFT → VALIDATING → PLANNING → PLAN_READY → APPROVED → APPLYING → APPLIED
```

Each state has specific rules about what actions are allowed.
