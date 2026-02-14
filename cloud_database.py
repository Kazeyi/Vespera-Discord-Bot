# --- Cloud Infrastructure Database Module ---
"""
ChatOps Infrastructure Provisioning Database
Manages cloud deployments, quotas, policies, and ephemeral sessions
"""

import sqlite3
import os
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

# Database file location
CLOUD_DB_FILE = os.path.abspath("cloud_infrastructure.db")

# Cache system for performance
_cache = {}
CACHE_TTL = 300  # 5 minutes for cloud data
MAX_CACHE_SIZE = 200

def get_cached(key: str) -> Optional[Any]:
    """Get item from cache if not expired"""
    if key in _cache:
        item = _cache[key]
        if time.time() - item['time'] < CACHE_TTL:
            return item['data']
        else:
            del _cache[key]
    return None

def set_cache(key: str, value: Any) -> None:
    """Set item in cache with TTL"""
    if len(_cache) >= MAX_CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[key] = {'data': value, 'time': time.time()}

def clear_cache(key: str = None) -> None:
    """Remove item from cache or clear all"""
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()


# --- DATABASE SCHEMA ---
CLOUD_SCHEMA = {
    # Cloud Projects Configuration
    "cloud_projects": """
        CREATE TABLE IF NOT EXISTS cloud_projects (
            project_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            provider TEXT NOT NULL CHECK(provider IN ('aws', 'gcp', 'azure')),
            project_name TEXT NOT NULL,
            region TEXT NOT NULL,
            budget_limit REAL DEFAULT 1000.0,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'deleted')),
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Quota Management (like D&D action limits)
    "cloud_quotas": """
        CREATE TABLE IF NOT EXISTS cloud_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            region TEXT,
            quota_limit INTEGER NOT NULL,
            quota_used INTEGER DEFAULT 0,
            quota_unit TEXT DEFAULT 'count',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (project_id) REFERENCES cloud_projects(project_id) ON DELETE CASCADE,
            UNIQUE(project_id, resource_type, region)
        )
    """,
    
    # Infrastructure Policies (like D&D action economy rules)
    "infrastructure_policies": """
        CREATE TABLE IF NOT EXISTS infrastructure_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            policy_name TEXT NOT NULL,
            policy_type TEXT NOT NULL CHECK(policy_type IN ('permission', 'quota', 'region', 'cost', 'security')),
            resource_pattern TEXT NOT NULL,
            allowed_values TEXT,
            denied_values TEXT,
            max_instances INTEGER,
            max_cost_per_hour REAL,
            require_approval BOOLEAN DEFAULT 0,
            priority INTEGER DEFAULT 100,
            is_active BOOLEAN DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            UNIQUE(guild_id, policy_name)
        )
    """,
    
    # User Permissions (like D&D class abilities)
    "user_cloud_permissions": """
        CREATE TABLE IF NOT EXISTS user_cloud_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role_name TEXT NOT NULL,
            provider TEXT CHECK(provider IN ('aws', 'gcp', 'azure', 'all')),
            can_create_vm BOOLEAN DEFAULT 0,
            can_create_db BOOLEAN DEFAULT 0,
            can_create_k8s BOOLEAN DEFAULT 0,
            can_create_network BOOLEAN DEFAULT 0,
            can_create_storage BOOLEAN DEFAULT 0,
            can_delete BOOLEAN DEFAULT 0,
            can_modify BOOLEAN DEFAULT 0,
            max_vm_size TEXT,
            max_db_size TEXT,
            allowed_regions TEXT,
            budget_limit REAL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            UNIQUE(user_id, guild_id, provider)
        )
    """,
    
    # Ephemeral Deployment Sessions (prevent memory leaks)
    "deployment_sessions": """
        CREATE TABLE IF NOT EXISTS deployment_sessions (
            session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            deployment_type TEXT NOT NULL,
            resources_pending TEXT,
            session_data TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'deploying', 'completed', 'failed', 'cancelled', 'expired')),
            expires_at REAL NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            completed_at REAL,
            FOREIGN KEY (project_id) REFERENCES cloud_projects(project_id) ON DELETE CASCADE
        )
    """,
    
    # Deployment History & Audit Log
    "deployment_history": """
        CREATE TABLE IF NOT EXISTS deployment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            resource_config TEXT,
            action TEXT NOT NULL CHECK(action IN ('create', 'modify', 'delete')),
            status TEXT NOT NULL,
            error_message TEXT,
            cost_estimate REAL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (session_id) REFERENCES deployment_sessions(session_id) ON DELETE SET NULL
        )
    """,
    
    # Infrastructure Resources (actual deployed resources)
    "cloud_resources": """
        CREATE TABLE IF NOT EXISTS cloud_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            region TEXT NOT NULL,
            zone TEXT,
            configuration TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            cost_per_hour REAL,
            created_by TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (project_id) REFERENCES cloud_projects(project_id) ON DELETE CASCADE
        )
    """,
    
    # Policy Validation Cache (like ActionEconomyValidator cache)
    "policy_cache": """
        CREATE TABLE IF NOT EXISTS policy_cache (
            cache_key TEXT PRIMARY KEY,
            validation_result TEXT NOT NULL,
            expires_at REAL NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Terraform State Tracking
    "terraform_states": """
        CREATE TABLE IF NOT EXISTS terraform_states (
            state_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            session_id TEXT,
            resource_id TEXT,
            tfstate_json TEXT NOT NULL,
            serial INTEGER DEFAULT 0,
            lineage TEXT,
            terraform_version TEXT,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (project_id) REFERENCES cloud_projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES deployment_sessions(session_id) ON DELETE SET NULL
        )
    """,
    
    # Audit Logging (comprehensive event tracking)
    "audit_logs": """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            project_id TEXT,
            session_id TEXT,
            resource_id TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            status TEXT DEFAULT 'success' CHECK(status IN ('success', 'failure', 'pending')),
            error_message TEXT,
            timestamp REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # Budget Alerts
    "budget_alerts": """
        CREATE TABLE IF NOT EXISTS budget_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            alert_threshold REAL NOT NULL,
            current_spending REAL DEFAULT 0.0,
            alert_triggered BOOLEAN DEFAULT 0,
            last_alert_at REAL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (project_id) REFERENCES cloud_projects(project_id) ON DELETE CASCADE
        )
    """,
    
    # Guild Policies (for multi-tenant policy enforcement)
    "guild_policies": """
        CREATE TABLE IF NOT EXISTS guild_policies (
            guild_id TEXT PRIMARY KEY,
            max_budget_monthly REAL DEFAULT 1000.0,
            max_instances INTEGER DEFAULT 10,
            allowed_instance_types TEXT DEFAULT '["e2-micro","e2-small","e2-medium","t3.micro","t3.small"]',
            allowed_resource_types TEXT DEFAULT '["vm","database","bucket","vpc"]',
            require_approval BOOLEAN DEFAULT 0,
            max_disk_size_gb INTEGER DEFAULT 500,
            iac_engine_preference TEXT DEFAULT 'terraform' CHECK(iac_engine_preference IN ('terraform', 'tofu')),
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """,
    
    # JIT Permissions (Just-In-Time permission grants with expiration)
    "jit_permissions": """
        CREATE TABLE IF NOT EXISTS jit_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            permission_level TEXT NOT NULL CHECK(permission_level IN ('viewer', 'deployer', 'admin')),
            granted_at REAL DEFAULT (strftime('%s', 'now')),
            expires_at REAL NOT NULL,
            granted_by TEXT,
            revoked BOOLEAN DEFAULT 0,
            revoked_at REAL
        )
    """,
    
    # Recovery Blobs (for ephemeral vault session recovery after crashes)
    "recovery_blobs": """
        CREATE TABLE IF NOT EXISTS recovery_blobs (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            encrypted_blob TEXT NOT NULL,
            deployment_status TEXT DEFAULT 'ACTIVE' CHECK(deployment_status IN ('ACTIVE', 'COMPLETED', 'FAILED')),
            created_at REAL DEFAULT (strftime('%s', 'now')),
            expires_at REAL NOT NULL
        )
    """
}


def init_cloud_database():
    """Initialize cloud infrastructure database with schema"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    # Create tables
    for table_name, schema in CLOUD_SCHEMA.items():
        cursor.execute(schema)
    
    # Create indexes separately (SQLite requirement)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_logs(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_logs(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jit_user_guild ON jit_permissions(user_id, guild_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jit_expires ON jit_permissions(expires_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jit_revoked ON jit_permissions(revoked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_user ON recovery_blobs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recovery_status ON recovery_blobs(deployment_status)")
    
    # Additional indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_guild ON cloud_projects(guild_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner ON cloud_projects(owner_user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotas_project ON cloud_quotas(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_policies_guild ON infrastructure_policies(guild_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_guild ON deployment_sessions(guild_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON deployment_sessions(status)")
    
    # Additional indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON deployment_sessions(expires_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_project ON deployment_history(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resources_project ON cloud_resources(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_user ON user_cloud_permissions(user_id, guild_id)")
    
    conn.commit()
    conn.close()
    print(f"✅ Cloud Infrastructure Database initialized: {CLOUD_DB_FILE}")


# --- PROJECT MANAGEMENT ---

def create_cloud_project(guild_id: str, owner_user_id: str, provider: str, 
                         project_name: str, region: str, budget_limit: float = 1000.0) -> str:
    """Create a new cloud project"""
    import uuid
    project_id = f"{provider}-{uuid.uuid4().hex[:12]}"
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO cloud_projects 
        (project_id, guild_id, owner_user_id, provider, project_name, region, budget_limit)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (project_id, guild_id, owner_user_id, provider, project_name, region, budget_limit))
    
    # Initialize default quotas
    default_quotas = [
        ('compute.instances', region, 10),
        ('compute.cpus', region, 24),
        ('compute.ram_gb', region, 64),
        ('database.instances', region, 5),
        ('storage.buckets', region, 20),
        ('network.vpcs', region, 5),
        ('network.load_balancers', region, 5),
    ]
    
    for resource_type, res_region, limit in default_quotas:
        cursor.execute("""
            INSERT INTO cloud_quotas (project_id, resource_type, region, quota_limit)
            VALUES (?, ?, ?, ?)
        """, (project_id, resource_type, res_region, limit))
    
    conn.commit()
    conn.close()
    
    clear_cache(f"project:{project_id}")
    return project_id


def get_cloud_project(project_id: str) -> Optional[Dict]:
    """Get cloud project details"""
    cache_key = f"project:{project_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM cloud_projects WHERE project_id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        set_cache(cache_key, result)
        return result
    return None


def list_user_projects(user_id: str, guild_id: str) -> List[Dict]:
    """List all projects owned by user in guild"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM cloud_projects 
        WHERE owner_user_id = ? AND guild_id = ? AND status = 'active'
        ORDER BY created_at DESC
    """, (user_id, guild_id))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# --- QUOTA MANAGEMENT ---

def check_quota(project_id: str, resource_type: str, region: str, requested_amount: int = 1) -> Tuple[bool, Dict]:
    """
    Check if quota allows the requested resource creation
    Returns: (can_deploy, quota_info)
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM cloud_quotas 
        WHERE project_id = ? AND resource_type = ? AND (region = ? OR region IS NULL)
        LIMIT 1
    """, (project_id, resource_type, region))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # No quota defined - deny by default
        return False, {
            'error': 'NO_QUOTA_DEFINED',
            'resource_type': resource_type,
            'message': f'No quota defined for {resource_type} in {region}'
        }
    
    quota = dict(row)
    available = quota['quota_limit'] - quota['quota_used']
    
    can_deploy = available >= requested_amount
    
    return can_deploy, {
        'quota_limit': quota['quota_limit'],
        'quota_used': quota['quota_used'],
        'available': available,
        'requested': requested_amount,
        'can_deploy': can_deploy
    }


def consume_quota(project_id: str, resource_type: str, region: str, amount: int = 1):
    """Consume quota when resource is deployed"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE cloud_quotas 
        SET quota_used = quota_used + ?, updated_at = strftime('%s', 'now')
        WHERE project_id = ? AND resource_type = ? AND (region = ? OR region IS NULL)
    """, (amount, project_id, resource_type, region))
    
    conn.commit()
    conn.close()
    
    clear_cache(f"quota:{project_id}:{resource_type}")


def release_quota(project_id: str, resource_type: str, region: str, amount: int = 1):
    """Release quota when resource is deleted"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE cloud_quotas 
        SET quota_used = MAX(0, quota_used - ?), updated_at = strftime('%s', 'now')
        WHERE project_id = ? AND resource_type = ? AND (region = ? OR region IS NULL)
    """, (amount, project_id, resource_type, region))
    
    conn.commit()
    conn.close()
    
    clear_cache(f"quota:{project_id}:{resource_type}")


# --- EPHEMERAL SESSION MANAGEMENT ---

def create_deployment_session(project_id: str, user_id: str, guild_id: str, 
                               channel_id: str, provider: str, deployment_type: str,
                               resources: List[Dict], timeout_minutes: int = 30) -> str:
    """
    Create ephemeral deployment session to prevent memory leaks
    Session auto-expires after timeout
    """
    import uuid
    session_id = f"deploy-{uuid.uuid4().hex[:16]}"
    expires_at = time.time() + (timeout_minutes * 60)
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO deployment_sessions 
        (session_id, project_id, user_id, guild_id, channel_id, provider, 
         deployment_type, resources_pending, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, project_id, user_id, guild_id, channel_id, provider,
          deployment_type, json.dumps(resources), expires_at))
    
    conn.commit()
    conn.close()
    
    return session_id


def get_deployment_session(session_id: str) -> Optional[Dict]:
    """Get deployment session with auto-expiry check"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM deployment_sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    
    if row:
        session = dict(row)
        
        # Check if expired
        if time.time() > session['expires_at'] and session['status'] == 'pending':
            cursor.execute("""
                UPDATE deployment_sessions 
                SET status = 'expired', completed_at = strftime('%s', 'now')
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            session['status'] = 'expired'
        
        conn.close()
        
        # Parse JSON fields
        if session.get('resources_pending'):
            session['resources_pending'] = json.loads(session['resources_pending'])
        
        return session
    
    conn.close()
    return None


def cleanup_expired_sessions():
    """Clean up expired sessions (run periodically)"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute("""
        UPDATE deployment_sessions 
        SET status = 'expired', completed_at = ?
        WHERE expires_at < ? AND status IN ('pending', 'approved')
    """, (current_time, current_time))
    
    expired_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if expired_count > 0:
        print(f"🧹 Cleaned up {expired_count} expired deployment sessions")
    
    return expired_count


def update_resource_config(resource_id: str, new_config: dict) -> bool:
    """Update resource configuration (for editing resources)"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE cloud_resources
            SET config = ?,
                updated_at = ?
            WHERE resource_id = ?
        """, (json.dumps(new_config), time.time(), resource_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        
        if success:
            clear_cache(f"resource_{resource_id}")
            print(f"✅ Updated resource config: {resource_id}")
        
        return success
    
    finally:
        conn.close()


def mark_resource_for_deletion(resource_id: str) -> bool:
    """Mark resource for deletion in next terraform apply"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE cloud_resources
            SET status = 'pending_deletion',
                updated_at = ?
            WHERE resource_id = ?
        """, (time.time(), resource_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        
        if success:
            clear_cache(f"resource_{resource_id}")
            print(f"💀 Marked resource for deletion: {resource_id}")
        
        return success
    
    finally:
        conn.close()


def complete_deployment_session(session_id: str, status: str = 'completed'):
    """Mark session as completed/failed/cancelled"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE deployment_sessions 
        SET status = ?, completed_at = strftime('%s', 'now')
        WHERE session_id = ?
    """, (status, session_id))
    
    conn.commit()
    conn.close()
    
    clear_cache(f"session:{session_id}")


# --- USER PERMISSIONS ---

def get_user_permissions(user_id: str, guild_id: str, provider: str = 'all') -> Optional[Dict]:
    """Get user's cloud infrastructure permissions"""
    cache_key = f"perms:{user_id}:{guild_id}:{provider}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM user_cloud_permissions 
        WHERE user_id = ? AND guild_id = ? AND (provider = ? OR provider = 'all')
        ORDER BY provider DESC
        LIMIT 1
    """, (user_id, guild_id, provider))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = dict(row)
        set_cache(cache_key, result)
        return result
    return None


def grant_user_permission(user_id: str, guild_id: str, role_name: str, provider: str = 'all', **permissions):
    """Grant cloud infrastructure permissions to user"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    # Build dynamic SQL for permissions
    perm_fields = ['user_id', 'guild_id', 'role_name', 'provider']
    perm_values = [user_id, guild_id, role_name, provider]
    
    for key, value in permissions.items():
        if key.startswith('can_') or key.startswith('max_') or key.startswith('allowed_'):
            perm_fields.append(key)
            perm_values.append(value)
    
    placeholders = ','.join(['?'] * len(perm_fields))
    fields_str = ','.join(perm_fields)
    
    cursor.execute(f"""
        INSERT OR REPLACE INTO user_cloud_permissions ({fields_str})
        VALUES ({placeholders})
    """, perm_values)
    
    conn.commit()
    conn.close()
    
    clear_cache(f"perms:{user_id}:{guild_id}:{provider}")


# --- INFRASTRUCTURE POLICIES ---

def create_policy(guild_id: str, policy_name: str, policy_type: str, 
                  resource_pattern: str, **kwargs) -> int:
    """Create infrastructure policy"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO infrastructure_policies 
        (guild_id, policy_name, policy_type, resource_pattern, 
         allowed_values, denied_values, max_instances, max_cost_per_hour, 
         require_approval, priority, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id, policy_name, policy_type, resource_pattern,
        kwargs.get('allowed_values'),
        kwargs.get('denied_values'),
        kwargs.get('max_instances'),
        kwargs.get('max_cost_per_hour'),
        kwargs.get('require_approval', 0),
        kwargs.get('priority', 100),
        kwargs.get('is_active', 1)
    ))
    
    policy_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    clear_cache(f"policies:{guild_id}")
    return policy_id


def get_guild_policies(guild_id: str, is_active: bool = True) -> List[Dict]:
    """Get all active policies for guild"""
    cache_key = f"policies:{guild_id}:{is_active}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if is_active:
        cursor.execute("""
            SELECT * FROM infrastructure_policies 
            WHERE guild_id = ? AND is_active = 1
            ORDER BY priority ASC
        """, (guild_id,))
    else:
        cursor.execute("""
            SELECT * FROM infrastructure_policies 
            WHERE guild_id = ?
            ORDER BY priority ASC
        """, (guild_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    result = [dict(row) for row in rows]
    set_cache(cache_key, result)
    return result


# --- RESOURCE TRACKING ---

def create_cloud_resource(project_id: str, provider: str, resource_type: str,
                          resource_name: str, region: str, config: Dict,
                          created_by: str, **kwargs) -> str:
    """Track deployed cloud resource"""
    import uuid
    resource_id = f"{provider}-{resource_type}-{uuid.uuid4().hex[:12]}"
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO cloud_resources 
        (resource_id, project_id, provider, resource_type, resource_name, 
         region, zone, configuration, cost_per_hour, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        resource_id, project_id, provider, resource_type, resource_name,
        region, kwargs.get('zone'), json.dumps(config), 
        kwargs.get('cost_per_hour'), created_by
    ))
    
    conn.commit()
    conn.close()
    
    return resource_id


def get_project_resources(project_id: str, resource_type: str = None) -> List[Dict]:
    """Get all resources for a project"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if resource_type:
        cursor.execute("""
            SELECT * FROM cloud_resources 
            WHERE project_id = ? AND resource_type = ? AND status = 'active'
            ORDER BY created_at DESC
        """, (project_id, resource_type))
    else:
        cursor.execute("""
            SELECT * FROM cloud_resources 
            WHERE project_id = ? AND status = 'active'
            ORDER BY created_at DESC
        """, (project_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# --- AUDIT LOGGING ---

def log_deployment(project_id: str, user_id: str, guild_id: str, provider: str,
                   resource_type: str, resource_name: str, action: str, 
                   status: str, **kwargs):
    """Log deployment action to audit trail"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO deployment_history 
        (session_id, project_id, user_id, guild_id, provider, resource_type,
         resource_name, resource_config, action, status, error_message, cost_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        kwargs.get('session_id'),
        project_id, user_id, guild_id, provider, resource_type, resource_name,
        kwargs.get('resource_config'),
        action, status,
        kwargs.get('error_message'),
        kwargs.get('cost_estimate')
    ))
    
    conn.commit()
    conn.close()


def get_deployment_history(project_id: str, limit: int = 50) -> List[Dict]:
    """Get deployment history for project"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM deployment_history 
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (project_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# Initialize database on module import
if not os.path.exists(CLOUD_DB_FILE):
    init_cloud_database()


# --- TERRAFORM STATE MANAGEMENT ---

def save_terraform_state(project_id: str, session_id: str, tfstate_json: str, 
                         resource_id: str = None, **kwargs) -> str:
    """
    Save Terraform state to database
    
    Args:
        project_id: Project identifier
        session_id: Deployment session ID
        tfstate_json: Terraform state as JSON string
        resource_id: Specific resource ID (optional)
        **kwargs: serial, lineage, terraform_version
    
    Returns:
        state_id
    """
    import uuid
    state_id = f"tfstate-{uuid.uuid4().hex[:16]}"
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO terraform_states
        (state_id, project_id, session_id, resource_id, tfstate_json, serial, lineage, terraform_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state_id,
        project_id,
        session_id,
        resource_id,
        tfstate_json,
        kwargs.get('serial', 0),
        kwargs.get('lineage'),
        kwargs.get('terraform_version', '1.0')
    ))
    
    conn.commit()
    conn.close()
    
    return state_id


def get_terraform_state(project_id: str, session_id: str = None) -> Optional[Dict]:
    """
    Get latest Terraform state for a project
    
    Args:
        project_id: Project identifier
        session_id: Optional session filter
    
    Returns:
        Dict with state data or None
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if session_id:
        cursor.execute("""
            SELECT * FROM terraform_states
            WHERE project_id = ? AND session_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (project_id, session_id))
    else:
        cursor.execute("""
            SELECT * FROM terraform_states
            WHERE project_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (project_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def update_terraform_state(state_id: str, tfstate_json: str, serial: int = None):
    """
    Update existing Terraform state
    
    Args:
        state_id: State identifier
        tfstate_json: Updated state JSON
        serial: New serial number
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    if serial is not None:
        cursor.execute("""
            UPDATE terraform_states
            SET tfstate_json = ?, serial = ?, updated_at = strftime('%s', 'now')
            WHERE state_id = ?
        """, (tfstate_json, serial, state_id))
    else:
        cursor.execute("""
            UPDATE terraform_states
            SET tfstate_json = ?, updated_at = strftime('%s', 'now')
            WHERE state_id = ?
        """, (tfstate_json, state_id))
    
    conn.commit()
    conn.close()


# --- ENHANCED AUDIT LOGGING ---

def log_audit_event(event_type: str, user_id: str, guild_id: str, action: str,
                   details: Dict = None, **kwargs) -> int:
    """
    Log comprehensive audit event
    
    Args:
        event_type: Type of event (deployment, permission_change, quota_update, etc.)
        user_id: User who performed action
        guild_id: Guild/server ID
        action: Specific action taken
        details: Additional context as dict
        **kwargs: project_id, session_id, resource_id, ip_address, user_agent, status, error_message
    
    Returns:
        Audit log ID
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO audit_logs
        (event_type, user_id, guild_id, project_id, session_id, resource_id,
         action, details, ip_address, user_agent, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_type,
        user_id,
        guild_id,
        kwargs.get('project_id'),
        kwargs.get('session_id'),
        kwargs.get('resource_id'),
        action,
        json.dumps(details) if details else None,
        kwargs.get('ip_address'),
        kwargs.get('user_agent'),
        kwargs.get('status', 'success'),
        kwargs.get('error_message')
    ))
    
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return log_id


def get_audit_logs(guild_id: str = None, user_id: str = None, project_id: str = None,
                   event_type: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    Query audit logs with filters
    
    Args:
        guild_id: Filter by guild
        user_id: Filter by user
        project_id: Filter by project
        event_type: Filter by event type
        limit: Max results
        offset: Pagination offset
    
    Returns:
        List of audit log entries
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    
    if guild_id:
        query += " AND guild_id = ?"
        params.append(guild_id)
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_deployment_statistics(guild_id: str = None, days: int = 30) -> Dict:
    """
    Get deployment statistics for analytics
    
    Args:
        guild_id: Filter by guild (None = all)
        days: Time window in days
    
    Returns:
        Dict with statistics
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cutoff_time = time.time() - (days * 86400)
    
    # Total deployments
    if guild_id:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_history
            WHERE guild_id = ? AND created_at >= ?
        """, (guild_id, cutoff_time))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_history
            WHERE created_at >= ?
        """, (cutoff_time,))
    
    total_deployments = cursor.fetchone()[0]
    
    # Successful deployments
    if guild_id:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_history
            WHERE guild_id = ? AND created_at >= ? AND status = 'completed'
        """, (guild_id, cutoff_time))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_history
            WHERE created_at >= ? AND status = 'completed'
        """, (cutoff_time,))
    
    successful_deployments = cursor.fetchone()[0]
    
    # Active sessions
    if guild_id:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_sessions
            WHERE guild_id = ? AND status IN ('pending', 'approved', 'deploying')
            AND expires_at > ?
        """, (guild_id, time.time()))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_sessions
            WHERE status IN ('pending', 'approved', 'deploying')
            AND expires_at > ?
        """, (time.time(),))
    
    active_sessions = cursor.fetchone()[0]
    
    # Top users
    if guild_id:
        cursor.execute("""
            SELECT user_id, COUNT(*) as deployment_count
            FROM deployment_history
            WHERE guild_id = ? AND created_at >= ?
            GROUP BY user_id
            ORDER BY deployment_count DESC
            LIMIT 10
        """, (guild_id, cutoff_time))
    else:
        cursor.execute("""
            SELECT user_id, COUNT(*) as deployment_count
            FROM deployment_history
            WHERE created_at >= ?
            GROUP BY user_id
            ORDER BY deployment_count DESC
            LIMIT 10
        """, (cutoff_time,))
    
    top_users = cursor.fetchall()
    
    # Top resource types
    if guild_id:
        cursor.execute("""
            SELECT resource_type, COUNT(*) as count
            FROM deployment_history
            WHERE guild_id = ? AND created_at >= ?
            GROUP BY resource_type
            ORDER BY count DESC
            LIMIT 10
        """, (guild_id, cutoff_time))
    else:
        cursor.execute("""
            SELECT resource_type, COUNT(*) as count
            FROM deployment_history
            WHERE created_at >= ?
            GROUP BY resource_type
            ORDER BY count DESC
            LIMIT 10
        """, (cutoff_time,))
    
    top_resources = cursor.fetchall()
    
    conn.close()
    
    return {
        'total_deployments': total_deployments,
        'successful_deployments': successful_deployments,
        'active_sessions': active_sessions,
        'success_rate': (successful_deployments / total_deployments * 100) if total_deployments > 0 else 0,
        'top_users': top_users,
        'top_resources': top_resources
    }


# --- BUDGET MANAGEMENT ---

def create_budget_alert(project_id: str, alert_threshold: float) -> int:
    """
    Create budget alert for a project
    
    Args:
        project_id: Project identifier
        alert_threshold: Spending threshold in USD
    
    Returns:
        Alert ID
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO budget_alerts (project_id, alert_threshold)
        VALUES (?, ?)
    """, (project_id, alert_threshold))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return alert_id


def check_budget_alert(project_id: str, current_spending: float) -> bool:
    """
    Check if budget alert should trigger
    
    Args:
        project_id: Project identifier
        current_spending: Current spending amount
        
    Returns:
        bool: True if alert should trigger
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT alert_threshold, alert_triggered
        FROM budget_alerts
        WHERE project_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (project_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False
    
    threshold, already_triggered = result
    
    # Trigger if spending exceeds threshold and hasn't been triggered yet
    return current_spending >= threshold and not already_triggered


# --- GUILD POLICIES (Multi-Tenant) ---

def get_guild_policies(guild_id: str) -> Optional[Dict]:
    """Get guild-specific cloud policies"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM guild_policies WHERE guild_id = ?
    """, (guild_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    policies = dict(row)
    
    # Parse JSON fields
    try:
        policies['allowed_instance_types'] = json.loads(policies['allowed_instance_types'])
        policies['allowed_resource_types'] = json.loads(policies['allowed_resource_types'])
    except:
        pass
    
    return policies


def set_guild_policies(guild_id: str, policies: Dict) -> bool:
    """Set or update guild cloud policies"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Convert lists to JSON
        allowed_instances = json.dumps(policies.get('allowed_instance_types', []))
        allowed_resources = json.dumps(policies.get('allowed_resource_types', []))
        
        cursor.execute("""
            INSERT INTO guild_policies (
                guild_id, max_budget_monthly, max_instances,
                allowed_instance_types, allowed_resource_types,
                require_approval, max_disk_size_gb, iac_engine_preference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                max_budget_monthly = excluded.max_budget_monthly,
                max_instances = excluded.max_instances,
                allowed_instance_types = excluded.allowed_instance_types,
                allowed_resource_types = excluded.allowed_resource_types,
                require_approval = excluded.require_approval,
                max_disk_size_gb = excluded.max_disk_size_gb,
                iac_engine_preference = excluded.iac_engine_preference,
                updated_at = strftime('%s', 'now')
        """, (
            guild_id,
            policies.get('max_budget_monthly', 1000.0),
            policies.get('max_instances', 10),
            allowed_instances,
            allowed_resources,
            policies.get('require_approval', 0),
            policies.get('max_disk_size_gb', 500),
            policies.get('iac_engine_preference', 'terraform')
        ))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error setting guild policies: {e}")
        conn.close()
        return False


def get_guild_resource_count(guild_id: str, resource_type: str = None) -> int:
    """Get count of resources deployed in a guild"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    if resource_type:
        cursor.execute("""
            SELECT COUNT(*) FROM cloud_resources r
            JOIN cloud_projects p ON r.project_id = p.project_id
            WHERE p.guild_id = ? AND r.resource_type = ? AND r.status != 'deleted'
        """, (guild_id, resource_type))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM cloud_resources r
            JOIN cloud_projects p ON r.project_id = p.project_id
            WHERE p.guild_id = ? AND r.status != 'deleted'
        """, (guild_id,))
    
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_engine_preference(guild_id: str) -> str:
    """Get guild's preferred IaC engine (terraform/tofu)"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT iac_engine_preference FROM guild_policies WHERE guild_id = ?
    """, (guild_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else "terraform"


# --- JIT PERMISSIONS (Just-In-Time Access) ---

def grant_jit_permission(
    user_id: str,
    guild_id: str,
    provider: str,
    permission_level: str,
    granted_by: str,
    duration_minutes: int = 60
) -> int:
    """
    Grant temporary permission to user
    
    Returns:
        permission_id
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    expires_at = time.time() + (duration_minutes * 60)
    
    cursor.execute("""
        INSERT INTO jit_permissions (
            user_id, guild_id, provider, permission_level,
            expires_at, granted_by
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, guild_id, provider, permission_level, expires_at, granted_by))
    
    perm_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    clear_cache(f"jit_perms_{user_id}_{guild_id}")
    
    return perm_id


def get_active_jit_permissions(user_id: str, guild_id: str) -> List[Dict]:
    """Get user's active (non-expired, non-revoked) JIT permissions"""
    cache_key = f"jit_perms_{user_id}_{guild_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached
    
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute("""
        SELECT * FROM jit_permissions
        WHERE user_id = ? AND guild_id = ?
          AND expires_at > ?
          AND revoked = 0
        ORDER BY granted_at DESC
    """, (user_id, guild_id, current_time))
    
    perms = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    set_cache(cache_key, perms)
    return perms


def get_expired_permissions() -> List[Dict]:
    """Get all expired JIT permissions that haven't been revoked yet"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute("""
        SELECT * FROM jit_permissions
        WHERE expires_at <= ? AND revoked = 0
    """, (current_time,))
    
    perms = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return perms


def revoke_jit_permission(user_id: str, guild_id: str, permission_id: int = None) -> bool:
    """Revoke JIT permission(s) for user"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        if permission_id:
            cursor.execute("""
                UPDATE jit_permissions
                SET revoked = 1, revoked_at = ?
                WHERE id = ? AND user_id = ? AND guild_id = ?
            """, (time.time(), permission_id, user_id, guild_id))
        else:
            # Revoke all active permissions for user in guild
            cursor.execute("""
                UPDATE jit_permissions
                SET revoked = 1, revoked_at = ?
                WHERE user_id = ? AND guild_id = ? AND revoked = 0
            """, (time.time(), user_id, guild_id))
        
        conn.commit()
        conn.close()
        
        clear_cache(f"jit_perms_{user_id}_{guild_id}")
        return True
    
    except Exception as e:
        print(f"Error revoking JIT permission: {e}")
        conn.close()
        return False


# --- RECOVERY BLOBS (Encrypted Handshake for Session Recovery) ---

def save_recovery_blob(session_id: str, user_id: str, guild_id: str, encrypted_blob: str, expires_at: float) -> bool:
    """
    Save encrypted recovery blob to database.
    Allows session recovery after bot crash.
    
    Args:
        session_id: Vault session ID
        user_id: User who created the session
        guild_id: Guild ID
        encrypted_blob: Base64-encoded encrypted recovery data
        expires_at: Expiration timestamp
    
    Returns:
        bool: True if saved successfully
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO recovery_blobs (
                session_id, user_id, guild_id, encrypted_blob,
                deployment_status, expires_at
            ) VALUES (?, ?, ?, ?, 'ACTIVE', ?)
        """, (session_id, user_id, guild_id, encrypted_blob, expires_at))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error saving recovery blob: {e}")
        conn.close()
        return False


def get_recovery_blob(session_id: str) -> Optional[Dict]:
    """Get recovery blob for session"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM recovery_blobs
        WHERE session_id = ? AND deployment_status = 'ACTIVE'
    """, (session_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_user_active_sessions(user_id: str, guild_id: str) -> List[Dict]:
    """
    Get all active sessions for user that need recovery.
    Called after bot restart to offer session recovery.
    
    Returns:
        List of active session metadata
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute("""
        SELECT * FROM recovery_blobs
        WHERE user_id = ? AND guild_id = ?
          AND deployment_status = 'ACTIVE'
          AND expires_at > ?
        ORDER BY created_at DESC
    """, (user_id, guild_id, current_time))
    
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return sessions


def update_recovery_blob_status(session_id: str, status: str) -> bool:
    """
    Update recovery blob deployment status.
    
    Args:
        session_id: Session ID
        status: New status (ACTIVE/COMPLETED/FAILED)
    
    Returns:
        bool: True if updated successfully
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE recovery_blobs
            SET deployment_status = ?
            WHERE session_id = ?
        """, (status, session_id))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error updating recovery blob status: {e}")
        conn.close()
        return False


def cleanup_expired_recovery_blobs() -> int:
    """Remove expired recovery blobs"""
    conn = sqlite3.connect(CLOUD_DB_FILE)
    cursor = conn.cursor()
    
    current_time = time.time()
    
    cursor.execute("""
        DELETE FROM recovery_blobs
        WHERE expires_at <= ? OR deployment_status IN ('COMPLETED', 'FAILED')
    """, (current_time,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted


def check_budget_alert(guild_id: str, project_id: str, current_cost: float) -> bool:
    """
    Check if budget alert should be triggered
    
    Returns:
        True if alert triggered
    """
    conn = sqlite3.connect(CLOUD_DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM budget_alerts
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (project_id,))
    
    alert = cursor.fetchone()
    
    if not alert:
        conn.close()
        return False
    
    should_alert = current_spending >= alert['alert_threshold'] and not alert['alert_triggered']
    
    if should_alert:
        cursor.execute("""
            UPDATE budget_alerts
            SET current_spending = ?, alert_triggered = 1, last_alert_at = strftime('%s', 'now')
            WHERE id = ?
        """, (current_spending, alert['id']))
        conn.commit()
    
    conn.close()
    
    return should_alert
