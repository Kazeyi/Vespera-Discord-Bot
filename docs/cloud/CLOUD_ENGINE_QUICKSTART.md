# Cloud Engine v2.0 - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites

1. **Terraform installed**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install terraform
   
   # MacOS
   brew install terraform
   
   # Verify installation
   terraform --version
   ```

2. **Database initialized**
   ```python
   # Run this once to create the database
   from cloud_database import CloudDatabase
   db = CloudDatabase()
   ```

3. **Bot configured**
   Update your `main.py`:
   ```python
   # Add these lines
   await bot.load_extension('cloud_engine.cogs.user_commands')
   await bot.load_extension('cloud_engine.cogs.admin_commands')
   
   # Sync commands
   await bot.tree.sync()
   ```

### First Deployment (5 Steps)

#### Step 1: Create a Project (Admin)

```
/cloud-create-project project_id:dev-project provider:gcp description:Development environment
```

#### Step 2: Grant Yourself Access (Admin)

```
/cloud-grant user:@yourself project:dev-project permission:deploy
```

#### Step 3: Start a Deployment

```
/cloud-deploy project:dev-project provider:gcp
```

This creates an interactive lobby:

```
☁️ Cloud Deployment: dev-project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provider: GCP
State: Planning

⏳ Planning in Progress
Running terraform plan...

Session ID: abc12345
Resources: 0 resources
Time Remaining: 30 minutes

[Add Resource] [Refresh] [Cancel]
```

#### Step 4: Add Resources

Click **[Add Resource]** and fill in the modal:

```
Resource Type: compute_vm
Resource Name: web-server-01
Machine Type: e2-medium
Region: us-central1
```

Click **[Refresh]** to see your resource added.

#### Step 5: Approve & Deploy

After a few seconds, the plan will complete:

```
📋 Terraform Plan
✅ Plan Complete
➕ Add: 1
🔄 Change: 0
➖ Destroy: 0

💰 Estimated Cost
$24.50/hour
$735.00/month

[Approve & Deploy] [Add Resource] [Cancel]
```

Click **[Approve & Deploy]**. A Discord thread will be created showing real-time terraform output:

```
🚀 Starting deployment...

terraform apply -no-color -auto-approve tfplan
google_compute_instance.web-server-01: Creating...
google_compute_instance.web-server-01: Still creating... [10s elapsed]
google_compute_instance.web-server-01: Creation complete after 45s

✅ Deployment completed successfully!
```

## 📋 Common Commands

### User Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/cloud-deploy` | Start new deployment | `/cloud-deploy project:dev provider:gcp` |
| `/cloud-list` | List your deployments | `/cloud-list` |
| `/cloud-quota` | Check quotas | `/cloud-quota project:dev` |
| `/cloud-projects` | List available projects | `/cloud-projects` |
| `/cloud-cancel` | Cancel a deployment | `/cloud-cancel session_id:abc12345` |

### Admin Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/cloud-grant` | Grant permissions | `/cloud-grant user:@john project:dev permission:deploy` |
| `/cloud-revoke` | Revoke permissions | `/cloud-revoke user:@john project:dev` |
| `/cloud-create-project` | Create project | `/cloud-create-project project_id:prod provider:aws` |
| `/cloud-set-quota` | Set quotas | `/cloud-set-quota project:dev resource_type:compute_vm limit:20` |
| `/cloud-admin-list` | View all deployments | `/cloud-admin-list` |
| `/cloud-stats` | View statistics | `/cloud-stats` |

## 🎯 Usage Examples

### Example 1: Deploy a Web Server

```
1. /cloud-deploy project:dev-project provider:gcp
2. Click [Add Resource]
   - Resource Type: compute_vm
   - Name: web-server-01
   - Machine Type: e2-medium
   - Region: us-central1
3. Wait for plan to complete
4. Review the plan (shows 1 resource to add)
5. Click [Approve & Deploy]
6. Watch the thread for real-time output
```

### Example 2: Deploy Database + VPC

```
1. /cloud-deploy project:prod provider:aws
2. Add VPC:
   - Resource Type: vpc
   - Name: prod-vpc
   - Region: us-east-1
3. Add Database:
   - Resource Type: database
   - Name: prod-db
   - Machine Type: db.t3.small
   - Region: us-east-1
4. Click [Refresh]
5. Review plan (shows 2 resources to add)
6. Click [Approve & Deploy]
```

### Example 3: Multi-Resource Deployment

```
1. /cloud-deploy project:staging provider:azure
2. Add resources one by one:
   - VM: app-server-01
   - VM: app-server-02
   - Database: staging-db
   - Storage: staging-bucket
3. Plan shows: "Plan: 4 to add, 0 to change, 0 to destroy"
4. Estimated cost: $125/month
5. Approve and deploy
```

## 🔐 Permission Levels

### Read Permission
- Can view projects
- Can check quotas
- **Cannot** deploy

### Deploy Permission
- Can create deployments
- Can add resources
- Can approve own deployments
- Limited by quotas

### Admin Permission
- Can grant/revoke permissions
- Can create projects
- Can set quotas
- Can cancel any deployment

## 💡 Best Practices

### 1. Always Review the Plan

The plan shows exactly what will change:
- **Add**: New resources being created
- **Change**: Existing resources being modified
- **Destroy**: Resources being deleted

Never approve without reviewing!

### 2. Watch the Cost Estimates

Plans include cost estimates:
- Hourly cost
- Monthly cost projection

If costs seem too high, cancel and review your resources.

### 3. Use Sessions Wisely

Sessions expire after 30 minutes. If you need more time:
- Save your resource configuration
- Create a new session when ready

### 4. Leverage Quotas

Admins should set appropriate quotas to prevent:
- Accidental over-provisioning
- Cost overruns
- Resource sprawl

Example quota setup:
```
/cloud-set-quota project:dev resource_type:compute_vm limit:5
/cloud-set-quota project:dev resource_type:database limit:2
/cloud-set-quota project:prod resource_type:compute_vm limit:20
```

### 5. Monitor Deployments

Use `/cloud-list` regularly to track:
- Active deployments
- Resource usage
- Session states

Admins can use `/cloud-admin-list` for org-wide visibility.

## 🎨 Understanding the Lobby View

The deployment lobby has several states:

### Draft State
```
State: Draft
📦 Resources: 0 resources

[Add Resource] [Refresh] [Cancel]
```
Add resources before planning.

### Planning State
```
State: Planning
⏳ Planning in Progress
Running terraform plan...

[Refresh] [Cancel]
```
Wait for plan to complete (usually 10-30 seconds).

### Plan Ready State
```
State: Plan Ready
📋 Terraform Plan
✅ Plan Complete
➕ Add: 3
🔄 Change: 0
➖ Destroy: 0

💰 Estimated Cost
$45.00/hour

[Approve & Deploy] [Add Resource] [Cancel]
```
Review the plan, then approve to deploy.

### Applying State
```
State: Applying
🚀 Deployment in progress...
Check the thread below for real-time output

[Refresh]
```
Deployment running. Thread shows live terraform output.

### Applied State
```
State: Applied
✅ Deployment completed successfully!
Resources: 3 deployed

Created at: 2024-01-15 14:30:00
```
Deployment complete!

## 🔧 Troubleshooting

### Issue: "Session expired"
**Cause:** Sessions auto-expire after 30 minutes  
**Solution:** Create a new session with `/cloud-deploy`

### Issue: "Quota exceeded"
**Cause:** Project has hit resource limits  
**Solution:** Check quotas with `/cloud-quota project:your-project`

### Issue: "Permission denied"
**Cause:** User doesn't have deploy permission  
**Solution:** Ask admin to run `/cloud-grant @you project:project permission:deploy`

### Issue: "Plan failed"
**Cause:** Invalid terraform configuration  
**Solution:** Check resource configurations, verify provider credentials

### Issue: "Apply failed"
**Cause:** Terraform apply error  
**Solution:** Check the thread output for error details

## 📊 Monitoring & Statistics

### View Your Deployments
```
/cloud-list
```

Shows:
- Session states
- Resource counts
- Expiry times

### Check Quotas
```
/cloud-quota project:your-project
```

Shows progress bars:
```
Compute VMs
[████████░░] 8/10 (80%)

Databases
[████░░░░░░] 2/5 (40%)
```

### Admin Statistics
```
/cloud-stats
```

Shows:
- Total deployments
- Success rate
- Top users
- Most deployed resources

## 🚀 Advanced Usage

### Using the Orchestrator Directly

For custom workflows, use the orchestrator in your code:

```python
from cloud_engine import CloudOrchestrator
from cloud_database import CloudDatabase

# Initialize
db = CloudDatabase()
orchestrator = CloudOrchestrator(db)

# Start session
session = await orchestrator.start_session(
    user_id=123456789,
    project_id='my-project',
    provider='gcp',
    ttl_minutes=60  # Custom expiry
)

# Add resources
orchestrator.add_resource(session.id, 'compute_vm', {
    'name': 'worker-01',
    'machine_type': 'e2-standard-2',
    'region': 'us-central1'
})

# Validate
validation = await orchestrator.validate_session(session.id)

if validation['is_valid']:
    # Run plan
    plan = await orchestrator.run_plan(session.id)
    
    # Auto-approve if under budget
    if plan.monthly_cost < 100:
        await orchestrator.approve_and_apply(session.id, user_id)
```

### Session Lifecycle

```
DRAFT → VALIDATING → PLANNING → PLAN_READY → APPROVED → APPLYING → APPLIED
   ↓         ↓            ↓          ↓           ↓          ↓          ↓
FAILED ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

Each state has specific allowed operations:
- **DRAFT**: Can add resources, can start validation
- **PLANNING**: Cannot modify, wait for plan
- **PLAN_READY**: Can approve, can add more resources
- **APPROVED**: Locked, apply starting
- **APPLYING**: Locked, deployment in progress
- **APPLIED**: Complete, read-only

## 📚 Next Steps

1. ✅ Complete first deployment
2. ✅ Grant permissions to team members
3. ✅ Set up quotas for cost control
4. ✅ Create projects for different environments (dev, staging, prod)
5. ✅ Integrate with your CI/CD pipeline

## 🤝 Getting Help

If you need help:
1. Check this guide
2. Review the migration guide: `CLOUD_ENGINE_MIGRATION.md`
3. Check the logs for error messages
4. Test with a simple deployment first

---

**Version:** 2.0.0  
**Architecture:** Orchestrator Pattern with Plan-First Workflow  
**Modeled After:** D&D ActionEconomyValidator (Truth Block validation)
