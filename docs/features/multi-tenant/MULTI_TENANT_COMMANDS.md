# Multi-Tenant Security Commands - Quick Reference

## 🔐 Ephemeral Vault Commands

### /cloud-init - Secure Project Initialization
Initialize a new cloud project with zero-knowledge vault protection.

**Parameters:**
- `provider` - Cloud provider (gcp/aws/azure)
- `project_name` - Human-readable project name (stored in DB)
- `project_id` - **SENSITIVE**: Cloud provider project ID (encrypted in RAM only)
- `region` - Cloud region

**Example:**
```
/cloud-init provider:gcp 
           project_name:"Production API" 
           project_id:"my-gcp-project-123456" 
           region:"us-central1"
```

**Response:**
```
🔐 Secure Cloud Project Initialized
🔑 Vault Session: a1b2c3d4e5f6g7h8
📋 Project Name: Production API
☁️ Provider: GCP
🌍 Region: us-central1
💰 Budget Limit: $1,000/month
🛠️ IaC Engine: terraform

🔒 Security Notice:
✅ Project ID encrypted in memory (NOT saved to database)
⏰ Session expires in 30 minutes
🔐 Zero-knowledge architecture protects against backup leaks
```

**Security:**
- ✅ Project ID **never** stored in database
- ✅ Encrypted with unique Fernet key per session
- ✅ Auto-expires after 30 minutes
- ✅ No disk persistence (RAM only)

---

## 📜 Guild Policy Commands (Admin Only)

### /cloud-guild-policy - Manage Server Policies

**View Current Policies:**
```
/cloud-guild-policy action:view
```

**Update Policies:**
```
/cloud-guild-policy action:update max_budget:2000 max_instances:20 engine:tofu
```

**Parameters:**
- `action` - `view` or `update`
- `max_budget` - Maximum monthly budget in USD (default: 1000)
- `max_instances` - Maximum concurrent instances (default: 10)
- `engine` - Preferred IaC engine (`terraform` or `tofu`)

**View Response:**
```
📜 Guild Cloud Policies
Custom policies for ACME Corp

💰 Max Budget/Month: $2,000
🖥️ Max Instances: 20
💾 Max Disk Size: 500 GB
🛠️ IaC Engine: tofu
✅ Require Approval: No
📊 Active Resources: 5/20
```

**Update Response:**
```
✅ Guild Policies Updated
Cloud policies updated for ACME Corp

💰 Max Budget/Month: $2,000
🖥️ Max Instances: 20
🛠️ IaC Engine: tofu
```

**Policy Fields:**
- `max_budget_monthly` - Monthly spending limit (USD)
- `max_instances` - Maximum concurrent instances
- `max_disk_size_gb` - Maximum disk size per resource
- `allowed_instance_types` - Whitelist of instance types (empty = all allowed)
- `allowed_resource_types` - Whitelist of resource types (empty = all allowed)
- `require_approval` - Require admin approval for new projects
- `iac_engine_preference` - `terraform` or `tofu`

---

## 🔑 JIT Permission Commands (Admin Only)

### /cloud-jit-grant - Grant Temporary Permissions

Grant time-limited cloud access that auto-expires.

**Parameters:**
- `user` - User to grant permissions to
- `provider` - Cloud provider (gcp/aws/azure)
- `level` - Permission level (viewer/deployer/admin)
- `duration` - Duration in minutes (default: 60)

**Example:**
```
/cloud-jit-grant user:@contractor 
                provider:gcp 
                level:deployer 
                duration:120
```

**Response:**
```
✅ JIT Permission Granted
Temporary access granted to @contractor

☁️ Provider: Google Cloud (GCP)
🔐 Level: Deployer (Create/Update)
⏰ Duration: 120 min
📋 Permission ID: 42
```

**User Receives DM:**
```
🔑 JIT Permission Granted
You've been granted Deployer access to Google Cloud (GCP) 
in server "ACME Corp"

⏰ Expires in: 120 minutes
📋 Permission ID: 42
👤 Granted by: @admin
```

**Permission Levels:**
- `viewer` - Read-only access (list resources)
- `deployer` - Create/update resources
- `admin` - Full control (delete, modify policies)

---

### /cloud-jit-revoke - Revoke Temporary Permissions

Immediately revoke all active JIT permissions for a user.

**Parameters:**
- `user` - User to revoke permissions from

**Example:**
```
/cloud-jit-revoke user:@contractor
```

**Response:**
```
✅ Revoked all JIT permissions for @contractor
```

**User Receives DM:**
```
🔒 JIT Permissions Revoked
All your temporary cloud permissions in "ACME Corp" 
have been revoked by an administrator.
```

---

## 🚀 Deployment Commands (Updated)

### /cloud-deploy-v2 - Deploy with Policy Enforcement

Deploy infrastructure with automatic guild policy validation.

**Parameters:**
- `project_id` - Project ID (or session_id from /cloud-init)
- `resource_type` - Type of resource (vm/database/bucket/vpc/k8s)

**Example:**
```
/cloud-deploy-v2 project_id:abc123 resource_type:vm
```

**Flow:**
1. Select provider (GCP/AWS/Azure)
2. Select region (dynamic based on provider)
3. Select machine type (dynamic based on provider)
4. **Policy validation** (automatic)
5. Configure specs (name, disk, tags)
6. AI validation (if enabled)
7. Deploy

**Policy Enforcement:**
If deployment violates guild policies:
```
⛔ Policy Violation
Estimated monthly cost ($1,200) exceeds guild budget limit ($500)

Contact a server administrator to request policy changes.
```

**Policy Checks:**
- ✅ Budget limit (estimated monthly cost)
- ✅ Instance count (current vs. max)
- ✅ Disk size (requested vs. max)
- ✅ Instance type whitelist
- ✅ Resource type whitelist

---

## 🩺 Monitoring Commands

### /cloud-health - Check Cog Status

View cloud cog health metrics including vault status.

**Example:**
```
/cloud-health
```

**Response:**
```
🩺 Cloud Cog Health Status

💾 Memory Usage: 125.4 MB
⚡ CPU Usage: 3.2%
📊 Database Size: 45.8 MB
🔄 Active Sessions: 3
🧵 Threads: 8
🤖 AI Status: Available
🔐 Vault Sessions: 2

✅ All systems operational
```

---

## 🔍 Permission Checking

### Check Your JIT Permissions

Users can check their active permissions:

```python
# In Python/SQLite
SELECT * FROM jit_permissions 
WHERE user_id = 'YOUR_USER_ID' 
  AND guild_id = 'GUILD_ID' 
  AND revoked = 0 
  AND expires_at > strftime('%s', 'now');
```

**Fields:**
- `permission_level` - viewer/deployer/admin
- `provider` - gcp/aws/azure
- `granted_at` - Unix timestamp
- `expires_at` - Unix timestamp
- `granted_by` - User ID of admin who granted

---

## 🎛️ Administrative Tasks

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

### View Expired (Not Yet Revoked) Permissions

```sql
SELECT * FROM jit_permissions 
WHERE revoked = 0 AND expires_at <= strftime('%s', 'now');
```

**Note:** Should return 0 rows if JIT Janitor is working correctly.

### Check Resource Count Per Guild

```sql
SELECT p.guild_id, COUNT(*) as resource_count
FROM cloud_resources r
JOIN cloud_projects p ON r.project_id = p.project_id
WHERE r.status != 'deleted'
GROUP BY p.guild_id;
```

---

## ⚙️ Background Tasks

### Session Cleanup (Every 5 minutes)

Automatically cleans up:
- ✅ Expired deployment sessions
- ✅ Expired vault sessions (30+ minutes old)

**Logs:**
```
🧹 [CloudCog] Cleaned up 3 expired deployment sessions
🔐 [Vault] Purged 2 expired sessions (older than 30 minutes)
```

### JIT Permission Janitor (Every 1 minute)

Automatically:
- ✅ Finds expired JIT permissions
- ✅ Revokes them (sets `revoked=1`)
- ✅ Sends DM notification to users
- ✅ Logs revocations

**Logs:**
```
🔐 [JIT Janitor] Revoked 1 expired permissions
  - user_123456 (deployer, gcp) expired 5 minutes ago
```

**User Notification:**
```
⏰ JIT Permission Expired
Your deployer permission for Google Cloud (GCP) 
in server "ACME Corp" has expired and been revoked.
Duration: 60 minutes
```

---

## 📊 Policy Enforcement Examples

### Example 1: Budget Limit

**Guild Policy:**
```json
{"max_budget_monthly": 500}
```

**User tries to deploy:**
- Instance: n1-standard-32 (32 CPU, 120 GB RAM)
- Estimated cost: $1,200/month

**Result:**
```
⛔ Policy Violation
Estimated monthly cost ($1,200) exceeds guild budget limit ($500)
```

---

### Example 2: Instance Count Limit

**Guild Policy:**
```json
{"max_instances": 5}
```

**User tries to deploy 6th instance:**

**Result:**
```
⛔ Policy Violation
Guild has reached maximum instance limit (5)
```

---

### Example 3: Instance Type Whitelist

**Guild Policy:**
```json
{
  "allowed_instance_types": ["e2-micro", "e2-small", "n1-standard-1"]
}
```

**User tries to deploy:**
- Instance: n1-standard-16 (not in whitelist)

**Result:**
```
⛔ Policy Violation
Instance type 'n1-standard-16' not in guild whitelist: 
['e2-micro', 'e2-small', 'n1-standard-1']
```

---

### Example 4: Disk Size Limit

**Guild Policy:**
```json
{"max_disk_size_gb": 100}
```

**User tries to deploy:**
- Disk size: 500 GB

**Result:**
```
⛔ Policy Violation
Disk size (500 GB) exceeds guild limit (100 GB)
```

---

## 🔐 Security Best Practices

### 1. Always Use Ephemeral Vault

```bash
# ❌ BAD - Storing project_id in plain DB
/old-cloud-init project_id:"my-secret-project"

# ✅ GOOD - Using ephemeral vault
/cloud-init project_id:"my-secret-project"  # Encrypted in RAM
```

### 2. Set Guild Policies

```bash
# ✅ Set budget limits to prevent cost overruns
/cloud-guild-policy action:update max_budget:1000 max_instances:10
```

### 3. Use JIT Permissions

```bash
# ✅ Grant temporary access instead of permanent
/cloud-jit-grant user:@contractor level:deployer duration:60

# Not permanent role assignment
```

### 4. Choose IaC Engine

```bash
# ✅ Use OpenTofu for open-source compliance
/cloud-guild-policy action:update engine:tofu
```

---

## 🧪 Testing Commands

### Test Vault Expiration

```bash
1. /cloud-init project_id:"test123" ...
2. Wait 31 minutes
3. Try to deploy (should fail with "Session expired")
```

### Test Policy Enforcement

```bash
1. /cloud-guild-policy action:update max_budget:100
2. Try to deploy expensive instance (should block)
3. /cloud-guild-policy action:update max_budget:5000
4. Retry deployment (should succeed)
```

### Test JIT Expiration

```bash
1. /cloud-jit-grant user:@testuser level:deployer duration:1
2. Wait 2 minutes
3. Check jit_permissions table (should be revoked)
```

---

## 📚 Command Permissions

| Command | Required Permission | Notes |
|---------|-------------------|-------|
| `/cloud-init` | None | All users can initialize projects |
| `/cloud-deploy-v2` | None | Policy enforcement automatic |
| `/cloud-guild-policy` | **Administrator** | Server admins only |
| `/cloud-jit-grant` | **Administrator** | Server admins only |
| `/cloud-jit-revoke` | **Administrator** | Server admins only |
| `/cloud-health` | None | All users can view health |

---

## 🎯 Use Cases

### Use Case 1: Contractor Onboarding

```bash
# Day 1: Grant 8-hour access
/cloud-jit-grant user:@contractor provider:gcp level:deployer duration:480

# Day 5: Auto-expires, no manual cleanup needed
```

### Use Case 2: Cost Control

```bash
# Set strict budget for dev environment
/cloud-guild-policy action:update max_budget:200 max_instances:3

# All dev deployments auto-validated
```

### Use Case 3: Multi-Engine Testing

```bash
# Test with OpenTofu
/cloud-guild-policy action:update engine:tofu
/cloud-deploy-v2 ...

# Switch back to Terraform
/cloud-guild-policy action:update engine:terraform
```

### Use Case 4: Break-Glass Access

```bash
# Emergency: Grant admin access for 15 minutes
/cloud-jit-grant user:@oncall provider:aws level:admin duration:15

# Auto-revokes after incident resolved
```

---

**Last Updated**: 2025-01-XX  
**Bot Version**: Cloud ChatOps v3.0 (Multi-Tenant Edition)  
**See Also**: [MULTI_TENANT_SECURITY_GUIDE.md](./MULTI_TENANT_SECURITY_GUIDE.md)
