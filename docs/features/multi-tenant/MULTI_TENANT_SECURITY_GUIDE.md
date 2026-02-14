# Multi-Tenant Security & Ephemeral Vault Guide

## 🔐 Universal Bot Architecture

This bot now implements **enterprise-grade multi-tenancy** with **zero-knowledge encryption** for sensitive cloud credentials. The architecture prevents data leaks, enforces per-guild policies, and auto-expires permissions.

---

## 🌟 Key Features

### 1. **Ephemeral Vault (Zero-Knowledge Entry)**

Project IDs are **never stored in the database**. They're encrypted in RAM only with unique Fernet keys per session.

**Why?**
- Database backups could leak project IDs
- Stolen databases expose all credentials
- Compliance with zero-knowledge architecture

**How it works:**
```
User runs: /cloud-init project_id="my-gcp-project-123456"
                   ↓
System generates session_id (SHA256 hash)
                   ↓
Project ID encrypted with unique Fernet key
                   ↓
Stored in RAM only (_active_vaults dict)
                   ↓
Database stores: session_id (NOT project_id)
                   ↓
After 30 minutes: Auto-purged from memory
```

**Key Points:**
- ✅ Project IDs encrypted in memory
- ✅ Auto-expires after 30 minutes
- ✅ No disk persistence
- ✅ Survives restarts (requires re-init)

---

### 2. **Multi-Tenant State Isolation**

Each Discord **guild (server)** gets isolated Terraform state paths. No collisions between different servers using the same project names.

**Directory Structure:**
```
deployments/
├── guild_123456789/
│   ├── project_A/
│   │   ├── terraform.tfstate
│   │   └── backend.tf
│   └── project_B/
│       ├── terraform.tfstate
│       └── backend.tf
└── guild_987654321/
    └── project_A/  # Same name, different guild - NO CONFLICT
        ├── terraform.tfstate
        └── backend.tf
```

**Backend Configuration:**
- **GCS**: `tenants/{guild_id}/terraform/state/{project_id}`
- **S3**: `terraform-state/{guild_id}/{project_id}/terraform.tfstate`
- **Azure**: `{guild_id}-{project_id}-tfstate`

---

### 3. **Guild-Level Policy Guardrails**

Server administrators can set **per-server resource limits** to control costs and prevent abuse.

**Default Policies:**
```json
{
  "max_budget_monthly": 1000.0,        // Max $1,000/month
  "max_instances": 10,                  // Max 10 concurrent instances
  "max_disk_size_gb": 500,              // Max 500 GB disk
  "allowed_instance_types": [],         // All allowed (or restrict to ["n1-standard-1", "e2-micro"])
  "allowed_resource_types": [],         // All allowed (or restrict to ["vm", "bucket"])
  "require_approval": false,            // Admin approval required?
  "iac_engine_preference": "terraform"  // "terraform" or "tofu"
}
```

**Commands:**
```bash
# View current policies
/cloud-guild-policy action:view

# Update policies (Admin only)
/cloud-guild-policy action:update max_budget:2000 max_instances:20 engine:tofu
```

**Enforcement:**
- All deployments validated against guild policies **before** execution
- Blocks deployments that exceed budget/instance limits
- Shows helpful error message to user
- Administrator can override by updating policies

---

### 4. **JIT Permission Janitor (Auto-Expiration)**

**Just-In-Time (JIT)** permissions grant temporary access that **auto-expires** after a set duration.

**Use Cases:**
- Contractors need temporary access
- Break-glass scenarios (emergency access)
- Prevent permission creep

**Commands:**
```bash
# Grant temporary permission (Admin only)
/cloud-jit-grant user:@bob provider:gcp level:deployer duration:60

# Revoke all JIT permissions for user (Admin only)
/cloud-jit-revoke user:@bob
```

**Permission Levels:**
- `viewer` - Read-only (list resources)
- `deployer` - Create/update resources
- `admin` - Full control (delete, modify policies)

**Auto-Revocation:**
- Background task runs every **1 minute**
- Finds expired permissions
- Revokes automatically
- Sends DM notification to user
- Logs all revocations

**Database Schema:**
```sql
jit_permissions (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  guild_id TEXT,
  provider TEXT,
  permission_level TEXT,
  granted_at REAL,
  expires_at REAL,
  granted_by TEXT,
  revoked BOOLEAN DEFAULT 0,
  revoked_at REAL
)
```

---

### 5. **Multi-Engine Logic Wrapper (Terraform/OpenTofu)**

Guilds can choose their preferred **Infrastructure-as-Code (IaC)** engine.

**Supported Engines:**
- **Terraform** (HashiCorp)
- **OpenTofu** (Community fork, Apache 2.0)

**How to Set:**
```bash
# Set guild preference
/cloud-guild-policy action:update engine:tofu

# Check available engines
IACEngineManager.get_available_engines()
# Returns: ["terraform", "tofu"]
```

**Automatic Fallback:**
- If guild prefers `tofu` but it's not installed → falls back to `terraform`
- Logs warning in console
- User sees friendly error message

**Execution:**
```python
iac_engine = IACEngineManager()

success, stdout, stderr = await iac_engine.execute_iac(
    guild_id="123456789",
    command_type="apply",
    work_dir="/deployments/guild_123456789/project_A",
    engine="tofu"  # or "terraform"
)
```

---

## 📋 Workflow Examples

### Example 1: Secure Project Initialization

```bash
1. User runs:
   /cloud-init provider:gcp 
              project_name:"Production API" 
              project_id:"my-secret-gcp-project-123456" 
              region:"us-central1"

2. System:
   - Generates session_id: "a1b2c3d4e5f6g7h8"
   - Encrypts project_id with Fernet key
   - Stores encrypted data in RAM (_active_vaults)
   - Saves to DB: project_name, region, session_id (NOT project_id)

3. User sees:
   ✅ Secure Cloud Project Initialized
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

### Example 2: Guild Policy Enforcement

```bash
1. Admin sets guild policies:
   /cloud-guild-policy action:update max_budget:500 max_instances:5

2. User tries to deploy expensive instance:
   /cloud-deploy-v2 project_id:abc resource_type:vm
   (Selects: n1-standard-32, 128GB RAM, $1,200/month)

3. System blocks:
   ⛔ Policy Violation
   Estimated monthly cost ($1,200) exceeds guild budget limit ($500)
   
   Contact a server administrator to request policy changes.
```

### Example 3: JIT Permission Grant

```bash
1. Admin grants temporary access:
   /cloud-jit-grant user:@contractor provider:aws level:deployer duration:120

2. Contractor receives DM:
   🔑 JIT Permission Granted
   You've been granted Deployer access to AWS in server "ACME Corp"
   
   ⏰ Expires in: 120 minutes
   📋 Permission ID: 42
   👤 Granted by: @admin

3. After 120 minutes, background janitor:
   - Revokes permission (sets revoked=1 in DB)
   - Sends DM to contractor:
     ⏰ JIT Permission Expired
     Your deployer permission for AWS in server "ACME Corp" has expired and been revoked.
     Duration: 120 minutes
```

---

## 🔧 Technical Implementation

### EphemeralVault Class

**File:** `cloud_security.py`

```python
class EphemeralVault:
    """Zero-knowledge encrypted vault for sensitive cloud credentials"""
    
    def __init__(self):
        self._active_vaults = {}  # In-memory storage only
        self._vault_lock = threading.Lock()
    
    def open_session(self, session_id: str, raw_data: dict) -> bool:
        """Encrypt and store data in RAM"""
        key = Fernet.generate_key()  # Unique key per session
        cipher = Fernet(key)
        encrypted = cipher.encrypt(json.dumps(raw_data).encode())
        
        self._active_vaults[session_id] = {
            'key': key,
            'encrypted_data': encrypted,
            'created_at': time.time()
        }
        return True
    
    def get_data(self, session_id: str) -> Optional[dict]:
        """Decrypt and retrieve data"""
        vault = self._active_vaults.get(session_id)
        if not vault:
            raise ValueError("Session expired or not found")
        
        # Check expiration (30 minutes)
        if time.time() - vault['created_at'] > 1800:
            self.purge_session(session_id)
            raise ValueError("Session expired")
        
        cipher = Fernet(vault['key'])
        decrypted = cipher.decrypt(vault['encrypted_data'])
        return json.loads(decrypted.decode())
    
    def cleanup_expired(self):
        """Remove expired sessions (called by background task)"""
        current_time = time.time()
        expired_sessions = [
            sid for sid, vault in self._active_vaults.items()
            if current_time - vault['created_at'] > 1800
        ]
        for sid in expired_sessions:
            self.purge_session(sid)
```

### PolicyEnforcer Class

**File:** `cloud_security.py`

```python
class PolicyEnforcer:
    """Enforce guild-level resource policies"""
    
    def validate_request(
        self,
        guild_id: str,
        resource_type: str,
        instance_type: str,
        estimated_cost: float,
        disk_size_gb: int
    ) -> Tuple[bool, str]:
        """Validate deployment against guild policies"""
        
        # Get guild policies (or use defaults)
        policies = cloud_db.get_guild_policies(guild_id)
        if not policies:
            policies = self.DEFAULT_POLICIES
        
        # Check budget
        if estimated_cost > policies['max_budget_monthly']:
            return False, f"Estimated monthly cost (${estimated_cost}) exceeds guild budget limit (${policies['max_budget_monthly']})"
        
        # Check instance count
        current_count = cloud_db.get_guild_resource_count(guild_id, resource_type)
        if current_count >= policies['max_instances']:
            return False, f"Guild has reached maximum instance limit ({policies['max_instances']})"
        
        # Check disk size
        if disk_size_gb > policies['max_disk_size_gb']:
            return False, f"Disk size ({disk_size_gb} GB) exceeds guild limit ({policies['max_disk_size_gb']} GB)"
        
        # Check allowed instance types
        allowed_instances = policies.get('allowed_instance_types', [])
        if allowed_instances and instance_type not in allowed_instances:
            return False, f"Instance type '{instance_type}' not in guild whitelist: {allowed_instances}"
        
        return True, "✅ Deployment approved by guild policies"
```

---

## 🚀 Deployment Integration

### Updated /cloud-deploy-v2 Flow

```
1. User fills deployment form
         ↓
2. PolicyEnforcer validates against guild policies
         ↓ (if blocked)
   ⛔ Show policy violation error
         ↓ (if approved)
3. AI Advisor validates specs (if enabled)
         ↓
4. Retrieve project_id from EphemeralVault (using session_id)
         ↓
5. Use MultiTenantStateManager to get isolated work directory
         ↓
6. Generate Terraform/OpenTofu code
         ↓
7. Use IACEngineManager to execute with guild's preferred engine
         ↓
8. Deploy infrastructure
         ↓
9. Update database with resource metadata
```

---

## 📊 Database Schema Additions

### guild_policies Table

```sql
CREATE TABLE guild_policies (
    guild_id TEXT PRIMARY KEY,
    max_budget_monthly REAL DEFAULT 1000.0,
    max_instances INTEGER DEFAULT 10,
    allowed_instance_types TEXT,  -- JSON array
    allowed_resource_types TEXT,  -- JSON array
    require_approval BOOLEAN DEFAULT 0,
    max_disk_size_gb INTEGER DEFAULT 500,
    iac_engine_preference TEXT DEFAULT 'terraform',
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
)
```

### jit_permissions Table

```sql
CREATE TABLE jit_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    permission_level TEXT NOT NULL,  -- viewer/deployer/admin
    granted_at REAL DEFAULT (strftime('%s', 'now')),
    expires_at REAL NOT NULL,
    granted_by TEXT NOT NULL,
    revoked BOOLEAN DEFAULT 0,
    revoked_at REAL,
    INDEX idx_jit_user_guild (user_id, guild_id),
    INDEX idx_jit_expires (expires_at)
)
```

---

## 🛡️ Security Best Practices

### 1. **Never Log Sensitive Data**

```python
# ❌ BAD
print(f"Project ID: {project_id}")

# ✅ GOOD
print(f"🔐 [Vault] Session {session_id} opened for {project_name}")
```

### 2. **Use Ephemeral Sessions**

```python
# ❌ BAD - Storing project_id in database
cloud_db.create_project(project_id="my-gcp-project")

# ✅ GOOD - Using ephemeral vault
ephemeral_vault.open_session(session_id, {'project_id': 'my-gcp-project'})
cloud_db.create_project(session_ref=session_id)  # Only store session_id
```

### 3. **Enforce Guild Policies**

```python
# Always validate before deployment
is_valid, message = policy_enforcer.validate_request(...)
if not is_valid:
    await interaction.followup.send(f"⛔ {message}", ephemeral=True)
    return
```

### 4. **Auto-Expire JIT Permissions**

```python
# Always specify expiration
cloud_db.grant_jit_permission(
    user_id=user_id,
    duration_minutes=60  # Never grant indefinite access
)
```

---

## 🧪 Testing

### Test 1: Vault Expiration

```python
# Create session
ephemeral_vault.open_session("test123", {'project_id': 'test-project'})

# Wait 31 minutes
time.sleep(1860)

# Should raise ValueError
try:
    data = ephemeral_vault.get_data("test123")
    print("❌ FAIL: Session should have expired")
except ValueError as e:
    print("✅ PASS: Session expired correctly")
```

### Test 2: Guild Policy Enforcement

```python
# Set strict policies
cloud_db.set_guild_policies("123456", {
    'max_budget_monthly': 100.0,
    'max_instances': 1
})

# Try to deploy expensive instance
is_valid, msg = policy_enforcer.validate_request(
    guild_id="123456",
    estimated_cost=500.0  # Exceeds budget
)

assert not is_valid
assert "exceeds guild budget" in msg
```

### Test 3: JIT Permission Auto-Revocation

```python
# Grant 1-minute permission
perm_id = cloud_db.grant_jit_permission(
    user_id="user123",
    guild_id="guild456",
    provider="gcp",
    permission_level="deployer",
    duration_minutes=1
)

# Wait 2 minutes
time.sleep(120)

# Check if revoked
perms = cloud_db.get_active_jit_permissions("user123", "guild456")
assert len(perms) == 0  # Should be auto-revoked
```

---

## 🔍 Monitoring & Debugging

### Check Vault Status

```python
# In cloud.py cleanup_sessions task
print(f"Active vault sessions: {len(ephemeral_vault._active_vaults)}")
for session_id, vault in ephemeral_vault._active_vaults.items():
    age_minutes = (time.time() - vault['created_at']) / 60
    print(f"  Session {session_id}: {age_minutes:.1f} minutes old")
```

### Check Guild Policies

```bash
# View current policies
/cloud-guild-policy action:view

# Check resource count
SELECT COUNT(*) FROM cloud_resources 
WHERE project_id IN (
  SELECT project_id FROM cloud_projects WHERE guild_id = '123456'
) AND status != 'deleted';
```

### Check JIT Permissions

```sql
-- Active permissions
SELECT * FROM jit_permissions 
WHERE revoked = 0 AND expires_at > strftime('%s', 'now');

-- Expired but not yet revoked (should be 0 after janitor runs)
SELECT * FROM jit_permissions 
WHERE revoked = 0 AND expires_at <= strftime('%s', 'now');
```

---

## 📚 References

- **Ephemeral Vault**: `cloud_security.py` (Lines 1-120)
- **Multi-Tenant State**: `cloud_security.py` (Lines 122-220)
- **Policy Enforcer**: `cloud_security.py` (Lines 222-320)
- **IaC Engine**: `cloud_security.py` (Lines 322-410)
- **Database Functions**: `cloud_database.py` (Lines 1220-1400)
- **Cloud Cog Integration**: `cogs/cloud.py`

---

## 🎉 Summary

This bot now implements **enterprise-grade security** with:

✅ **Zero-Knowledge Vault** - Project IDs never hit disk  
✅ **Multi-Tenant Isolation** - Each guild gets isolated state  
✅ **Guild Policies** - Per-server budget/resource limits  
✅ **JIT Permissions** - Auto-expiring temporary access  
✅ **Multi-Engine Support** - Terraform or OpenTofu  

**Ideal for:**
- Multi-tenant SaaS platforms
- Managed service providers
- Enterprise environments
- Security-conscious organizations
- Compliance requirements (SOC 2, ISO 27001)

---

**Created**: 2025-01-XX  
**Version**: 1.0  
**Bot Version**: Cloud ChatOps v3.0 (Multi-Tenant Edition)
