# Multi-Tenant Security - Quick Start Guide

## 🚀 5-Minute Setup

Get started with enterprise-grade multi-tenant security in 5 minutes!

---

## Step 1: Initialize Secure Project (30 seconds)

Instead of the old `/cloud-init`, use the **new secure vault handshake**:

```
/cloud-init 
  provider:gcp 
  project_name:"My Production API" 
  project_id:"my-gcp-project-123456" 
  region:"us-central1"
```

**What happens:**
- ✅ Project ID encrypted in RAM (NOT database)
- ✅ Session ID generated: `a1b2c3d4e5f6g7h8`
- ✅ Auto-expires in 30 minutes
- ✅ Guild policies applied automatically

**You'll see:**
```
🔐 Secure Cloud Project Initialized
🔑 Vault Session: a1b2c3d4e5f6g7h8
📋 Project Name: My Production API
☁️ Provider: GCP
🔒 Security Notice:
✅ Project ID encrypted in memory (NOT saved to database)
⏰ Session expires in 30 minutes
```

---

## Step 2: Set Guild Policies (1 minute) - Admin Only

Set spending limits and resource restrictions for your server:

```
/cloud-guild-policy 
  action:update 
  max_budget:1000 
  max_instances:10 
  engine:terraform
```

**Policy Options:**
- `max_budget` - Monthly spending limit (USD)
- `max_instances` - Maximum concurrent instances
- `engine` - `terraform` or `tofu` (OpenTofu)

**You'll see:**
```
✅ Guild Policies Updated
💰 Max Budget/Month: $1,000
🖥️ Max Instances: 10
🛠️ IaC Engine: terraform
```

**View current policies:**
```
/cloud-guild-policy action:view
```

---

## Step 3: Deploy Infrastructure (2 minutes)

Deploy with **automatic policy enforcement**:

```
/cloud-deploy-v2 
  project_id:abc123 
  resource_type:vm
```

**Interactive Flow:**
1. Select provider (GCP/AWS/Azure)
2. Select region (dynamic dropdown)
3. Select machine type (dynamic dropdown)
4. **Policy validation** (automatic - blocks if over budget)
5. Configure specs (name, disk, tags)
6. AI validation (if enabled)
7. Deploy!

**Policy enforcement example:**
```
⛔ Policy Violation
Estimated monthly cost ($1,200) exceeds guild budget limit ($1,000)

Contact a server administrator to request policy changes.
```

---

## Step 4: Grant Temporary Access (30 seconds) - Admin Only

Grant time-limited permissions to contractors/team members:

```
/cloud-jit-grant 
  user:@contractor 
  provider:gcp 
  level:deployer 
  duration:60
```

**Permission Levels:**
- `viewer` - Read-only (list resources)
- `deployer` - Create/update resources
- `admin` - Full control

**You'll see:**
```
✅ JIT Permission Granted
⏰ Duration: 60 minutes
📋 Permission ID: 42
```

**User receives DM:**
```
🔑 JIT Permission Granted
You've been granted Deployer access to Google Cloud (GCP)
⏰ Expires in: 60 minutes
```

**Auto-revocation:**
After 60 minutes, permission automatically revoked by background janitor.

---

## Step 5: Monitor Health (30 seconds)

Check system status:

```
/cloud-health
```

**You'll see:**
```
🩺 Cloud Cog Health Status
💾 Memory Usage: 125.4 MB
🔄 Active Sessions: 3
🔐 Vault Sessions: 2
🤖 AI Status: Available
✅ All systems operational
```

---

## 🔐 Key Security Features

### 1. Zero-Knowledge Vault
**Problem**: Project IDs in database → vulnerable to backup leaks  
**Solution**: Encrypted in RAM, auto-purges after 30 minutes

### 2. Multi-Tenant Isolation
**Problem**: Different servers clash on same project names  
**Solution**: Each guild gets isolated Terraform state

### 3. Guild Policies
**Problem**: No cost control  
**Solution**: Per-server budget/instance limits

### 4. JIT Permissions
**Problem**: Users keep admin access forever  
**Solution**: Auto-expiring temporary access

### 5. Multi-Engine Support
**Problem**: Vendor lock-in to Terraform  
**Solution**: Support OpenTofu (open-source fork)

---

## 📋 Common Use Cases

### Use Case 1: Development Team

**Scenario**: Dev team needs limited resources

**Setup:**
```bash
# Admin sets policies
/cloud-guild-policy action:update max_budget:200 max_instances:5

# Developers deploy (auto-blocked if over budget)
/cloud-deploy-v2 project_id:dev-project resource_type:vm
```

**Result**: All dev deployments validated against $200/month limit

---

### Use Case 2: Contractor Access

**Scenario**: Contractor needs temporary access for 2 hours

**Setup:**
```bash
# Grant 2-hour access
/cloud-jit-grant user:@contractor provider:gcp level:deployer duration:120

# After 2 hours: Auto-revokes, sends DM notification
```

**Result**: No manual cleanup needed

---

### Use Case 3: Multi-Team Organization

**Scenario**: Different Discord servers for different teams

**Setup:**
```bash
# Server A (Backend Team)
/cloud-guild-policy action:update max_budget:2000 engine:tofu

# Server B (Frontend Team)
/cloud-guild-policy action:update max_budget:500 engine:terraform
```

**Result**: Isolated budgets and preferences per team

---

### Use Case 4: Cost Control

**Scenario**: Finance team enforces $1,000/month limit

**Setup:**
```bash
# Set strict budget
/cloud-guild-policy action:update max_budget:1000

# User tries to deploy $1,200/month instance
/cloud-deploy-v2 ...

# Blocked:
⛔ Estimated monthly cost ($1,200) exceeds guild budget limit ($1,000)
```

**Result**: No surprise cloud bills

---

## 🛡️ Security Best Practices

### ✅ DO

1. **Always use /cloud-init** with vault (not old version)
2. **Set guild policies** to prevent cost overruns
3. **Use JIT permissions** instead of permanent roles
4. **Monitor /cloud-health** regularly
5. **Review policies monthly** (adjust budgets as needed)

### ❌ DON'T

1. **Don't log project IDs** (sensitive data)
2. **Don't grant permanent admin** (use JIT instead)
3. **Don't skip policy setup** (defaults may be too permissive)
4. **Don't share vault sessions** (unique per project)
5. **Don't disable JIT janitor** (needed for auto-revocation)

---

## 🧪 Quick Test

### Test 1: Vault Expiration (31 minutes)

```bash
1. /cloud-init project_id:"test123" ...
2. Wait 31 minutes
3. Try to deploy → Should fail with "Session expired"
```

### Test 2: Policy Enforcement (2 minutes)

```bash
1. /cloud-guild-policy action:update max_budget:100
2. Try to deploy expensive instance ($1,000/month)
3. Should block with "⛔ Policy Violation"
```

### Test 3: JIT Auto-Revocation (3 minutes)

```bash
1. /cloud-jit-grant user:@testuser level:deployer duration:1
2. Wait 2 minutes
3. Check: Permission auto-revoked, user got DM
```

---

## 🔍 Troubleshooting

### Issue: "Session expired or not found"

**Cause**: Vault session older than 30 minutes  
**Solution**: Re-run `/cloud-init` to create new session

---

### Issue: "Policy Violation: Budget limit exceeded"

**Cause**: Deployment cost exceeds guild budget  
**Solution**: 
- Option 1: Deploy cheaper instance
- Option 2: Ask admin to increase budget: `/cloud-guild-policy action:update max_budget:2000`

---

### Issue: "JIT permission not working"

**Cause**: Permission expired or revoked  
**Solution**: Check expiration time, request new grant from admin

---

### Issue: "Engine 'tofu' not found, falling back to terraform"

**Cause**: OpenTofu not installed  
**Solution**: 
- Option 1: Install OpenTofu
- Option 2: Use Terraform: `/cloud-guild-policy action:update engine:terraform`

---

## 📊 Admin Dashboard (SQL Queries)

### View All Guild Policies

```sql
SELECT guild_id, max_budget_monthly, max_instances, iac_engine_preference 
FROM guild_policies;
```

### View Active JIT Permissions

```sql
SELECT user_id, guild_id, provider, permission_level, 
       datetime(expires_at, 'unixepoch') as expires_at
FROM jit_permissions 
WHERE revoked = 0 AND expires_at > strftime('%s', 'now');
```

### View Resource Count Per Guild

```sql
SELECT p.guild_id, COUNT(*) as resource_count
FROM cloud_resources r
JOIN cloud_projects p ON r.project_id = p.project_id
WHERE r.status != 'deleted'
GROUP BY p.guild_id;
```

---

## 🎓 Learning Path

### Beginner (Day 1)
1. ✅ Use `/cloud-init` with vault
2. ✅ Deploy simple VM with `/cloud-deploy-v2`
3. ✅ Check health with `/cloud-health`

### Intermediate (Week 1)
1. ✅ Set guild policies (admin)
2. ✅ Grant JIT permissions (admin)
3. ✅ Test policy enforcement

### Advanced (Month 1)
1. ✅ Switch to OpenTofu
2. ✅ Set up multi-tenant isolation
3. ✅ Monitor vault sessions
4. ✅ Custom policy configurations

---

## 📚 References

- **Full Documentation**: [MULTI_TENANT_SECURITY_GUIDE.md](./MULTI_TENANT_SECURITY_GUIDE.md)
- **Command Reference**: [MULTI_TENANT_COMMANDS.md](./MULTI_TENANT_COMMANDS.md)
- **Implementation Details**: [MULTI_TENANT_IMPLEMENTATION_SUMMARY.md](./MULTI_TENANT_IMPLEMENTATION_SUMMARY.md)

---

## 🎉 You're Ready!

You now have:
- ✅ Zero-knowledge vault for sensitive data
- ✅ Multi-tenant state isolation
- ✅ Guild-level cost controls
- ✅ Auto-expiring temporary access
- ✅ Multi-engine support (Terraform/OpenTofu)

**Next Steps:**
1. Run `/cloud-init` with your first project
2. Set guild policies as admin
3. Deploy infrastructure with automatic validation
4. Grant temporary access to team members

**Questions?** Check the full documentation or run `/cloud-health` to verify system status.

---

**Created**: 2025-01-XX  
**Bot Version**: Cloud ChatOps v3.0 (Multi-Tenant Edition)  
**Status**: Production Ready ✅
