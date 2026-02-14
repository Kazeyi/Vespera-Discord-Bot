# --- Ephemeral Vault & Security Enhancements ---
"""
Advanced security features for Cloud ChatOps:
- Zero-knowledge ephemeral vault (in-memory encryption)
- Multi-tenant state isolation
- Guild-level policy enforcement
- JIT permission management
"""

import os
import time
import re
import base64
import hashlib
from typing import Optional, Dict, Tuple
from cryptography.fernet import Fernet
import json


class EphemeralVault:
    """
    Zero-knowledge ephemeral vault for sensitive data.
    Stores encrypted data in RAM only - no disk persistence.
    Each session gets a unique encryption key.
    """
    
    def __init__(self):
        # Stores: {session_id: {"key": FernetKey, "secret": EncryptedData, "created_at": timestamp, "recovery_blob": Optional}}
        # This stays in RAM only. If the bot restarts, it's gone.
        self._active_vaults = {}
        self._max_session_age = 1800  # 30 minutes
        self._recovery_enabled = True  # Enable recovery blob generation
    
    def open_session(self, session_id: str, raw_data: str) -> bool:
        """
        Create a new encrypted session.
        
        Args:
            session_id: Unique session identifier
            raw_data: Sensitive data to encrypt (e.g., project ID, credentials)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate unique encryption key for this session
            key = Fernet.generate_key()
            f = Fernet(key)
            
            # Encrypt the data
            encrypted_data = f.encrypt(raw_data.encode())
            
            # Store in memory
            self._active_vaults[session_id] = {
                "key": key,
                "secret": encrypted_data,
                "created_at": time.time()
            }
            
            return True
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to open session: {e}")
            return False
    
    def get_data(self, session_id: str) -> Optional[str]:
        """
        Retrieve and decrypt data from session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Decrypted data or None if session doesn't exist or expired
        """
        try:
            # Check if session exists
            vault_data = self._active_vaults.get(session_id)
            if not vault_data:
                return None
            
            # Check if session expired
            age = time.time() - vault_data["created_at"]
            if age > self._max_session_age:
                self.purge_session(session_id)
                return None
            
            # Decrypt and return
            f = Fernet(vault_data["key"])
            return f.decrypt(vault_data["secret"]).decode()
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to get data: {e}")
            return None
    
    def update_session(self, session_id: str, new_data: str) -> bool:
        """Update existing session with new data (re-encrypts with same key)"""
        try:
            vault_data = self._active_vaults.get(session_id)
            if not vault_data:
                return False
            
            # Re-encrypt with existing key
            f = Fernet(vault_data["key"])
            encrypted_data = f.encrypt(new_data.encode())
            
            vault_data["secret"] = encrypted_data
            vault_data["created_at"] = time.time()  # Reset timer
            
            return True
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to update session: {e}")
            return False
    
    def purge_session(self, session_id: str) -> bool:
        """Remove session from memory"""
        try:
            if session_id in self._active_vaults:
                del self._active_vaults[session_id]
                return True
            return False
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to purge session: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count of purged sessions."""
        purged = 0
        current_time = time.time()
        
        expired_sessions = [
            sid for sid, data in self._active_vaults.items()
            if current_time - data["created_at"] > self._max_session_age
        ]
        
        for session_id in expired_sessions:
            if self.purge_session(session_id):
                purged += 1
        
        return purged
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self._active_vaults)
    
    def generate_recovery_blob(self, session_id: str, user_passphrase: str) -> Optional[str]:
        """
        Generate encrypted recovery blob for session.
        This allows session recovery after bot crash using user's passphrase.
        
        Args:
            session_id: Session to generate recovery for
            user_passphrase: User's passphrase (e.g., user_id or custom PIN)
        
        Returns:
            Base64-encoded encrypted recovery blob or None if failed
        """
        try:
            raw_data = self.get_data(session_id)
            if not raw_data:
                return None
            
            # Derive encryption key from user passphrase (SHA-256)
            recovery_key = hashlib.sha256(user_passphrase.encode()).digest()
            recovery_key_b64 = base64.urlsafe_b64encode(recovery_key)
            
            # Encrypt with user's derived key
            f = Fernet(recovery_key_b64)
            encrypted_blob = f.encrypt(raw_data.encode())
            
            # Store recovery blob in session metadata
            if session_id in self._active_vaults:
                self._active_vaults[session_id]['recovery_blob'] = encrypted_blob
            
            # Return as base64 string for database storage
            return base64.b64encode(encrypted_blob).decode()
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to generate recovery blob: {e}")
            return None
    
    def recover_session(self, session_id: str, recovery_blob: str, user_passphrase: str) -> bool:
        """
        Recover session from encrypted recovery blob.
        Used after bot restart to restore active sessions.
        
        Args:
            session_id: Session ID to recover
            recovery_blob: Base64-encoded encrypted blob from database
            user_passphrase: User's passphrase to decrypt
        
        Returns:
            bool: True if recovery successful
        """
        try:
            # Decode blob
            encrypted_blob = base64.b64decode(recovery_blob.encode())
            
            # Derive key from passphrase
            recovery_key = hashlib.sha256(user_passphrase.encode()).digest()
            recovery_key_b64 = base64.urlsafe_b64encode(recovery_key)
            
            # Decrypt
            f = Fernet(recovery_key_b64)
            decrypted_data = f.decrypt(encrypted_blob).decode()
            
            # Create new session with recovered data
            return self.open_session(session_id, decrypted_data)
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to recover session: {e}")
            return False
    
    def store_service_account(self, session_id: str, sa_json: str) -> bool:
        """
        Store service account JSON in vault (for universal multi-tenant support).
        
        Args:
            session_id: Session ID
            sa_json: Service account JSON string
        
        Returns:
            bool: True if stored successfully
        """
        try:
            # Add to existing session data
            raw_data = self.get_data(session_id)
            if raw_data:
                # Parse existing data
                data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                data_dict['service_account'] = sa_json
                
                # Re-encrypt with updated data
                return self.update_session(session_id, json.dumps(data_dict))
            else:
                # Create new session
                return self.open_session(session_id, json.dumps({'service_account': sa_json}))
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to store service account: {e}")
            return False
    
    def get_service_account(self, session_id: str) -> Optional[str]:
        """
        Retrieve service account JSON from vault.
        
        Args:
            session_id: Session ID
        
        Returns:
            Service account JSON string or None
        """
        try:
            raw_data = self.get_data(session_id)
            if raw_data:
                data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                return data_dict.get('service_account')
            return None
        
        except Exception as e:
            print(f"[EphemeralVault] Failed to get service account: {e}")
            return None


class MultiTenantStateManager:
    """
    Manages terraform state isolation per Discord guild.
    Prevents resource collisions between different servers.
    """
    
    @staticmethod
    def get_tenant_backend_config(guild_id: str, project_id: str, provider: str = "gcp") -> Dict[str, str]:
        """
        Generate isolated terraform backend configuration per guild.
        
        Args:
            guild_id: Discord guild ID
            project_id: Cloud project ID
            provider: Cloud provider (gcp/aws/azure)
        
        Returns:
            Backend configuration dict
        """
        # Isolation pattern: tenants/{guild_id}/{project_id}
        prefix = f"tenants/{guild_id}/{project_id}"
        
        configs = {
            "gcp": {
                "backend_type": "gcs",
                "bucket": os.getenv("TF_STATE_BUCKET_GCP", "universal-bot-tf-state"),
                "prefix": prefix
            },
            "aws": {
                "backend_type": "s3",
                "bucket": os.getenv("TF_STATE_BUCKET_AWS", "universal-bot-tf-state"),
                "key": f"{prefix}/terraform.tfstate",
                "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                "dynamodb_table": "terraform-locks"
            },
            "azure": {
                "backend_type": "azurerm",
                "resource_group_name": "terraform-state",
                "storage_account_name": os.getenv("TF_STATE_STORAGE_AZURE", "tfstatebot"),
                "container_name": "tfstate",
                "key": f"{prefix}/terraform.tfstate"
            }
        }
        
        return configs.get(provider, configs["gcp"])
    
    @staticmethod
    def generate_backend_hcl(config: Dict[str, str]) -> str:
        """Generate HCL code for terraform backend"""
        backend_type = config.get("backend_type", "gcs")
        
        if backend_type == "gcs":
            return f'''
terraform {{
  backend "gcs" {{
    bucket = "{config["bucket"]}"
    prefix = "{config["prefix"]}"
  }}
}}
'''
        elif backend_type == "s3":
            return f'''
terraform {{
  backend "s3" {{
    bucket         = "{config["bucket"]}"
    key            = "{config["key"]}"
    region         = "{config["region"]}"
    dynamodb_table = "{config["dynamodb_table"]}"
  }}
}}
'''
        elif backend_type == "azurerm":
            return f'''
terraform {{
  backend "azurerm" {{
    resource_group_name  = "{config["resource_group_name"]}"
    storage_account_name = "{config["storage_account_name"]}"
    container_name       = "{config["container_name"]}"
    key                  = "{config["key"]}"
  }}
}}
'''
        
        return ""
    
    @staticmethod
    def get_work_directory(guild_id: str, project_id: str) -> str:
        """Get isolated working directory for guild's terraform operations"""
        base_dir = os.path.join("deployments", str(guild_id), project_id)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir


class PolicyEnforcer:
    """
    Guild-level policy enforcement for resource restrictions.
    Allows server admins to control costs and resource types.
    """
    
    DEFAULT_POLICIES = {
        "max_budget_monthly": 1000.0,  # USD per month
        "max_instances": 10,
        "allowed_instance_types": ["e2-micro", "e2-small", "e2-medium", "t3.micro", "t3.small"],
        "allowed_resource_types": ["vm", "database", "bucket", "vpc"],
        "require_approval": False,
        "max_disk_size_gb": 500
    }
    
    @staticmethod
    def validate_request(
        guild_id: str,
        resource_type: str,
        instance_type: str,
        estimated_cost_monthly: float,
        disk_size_gb: int = 20
    ) -> Tuple[bool, str]:
        """
        Validate deployment request against guild policies.
        
        Returns:
            (is_valid: bool, message: str)
        """
        try:
            # Import here to avoid circular dependency
            import cloud_database as cloud_db
            
            # Get guild-specific policies (or use defaults)
            policies = cloud_db.get_guild_policies(guild_id)
            if not policies:
                policies = PolicyEnforcer.DEFAULT_POLICIES
            
            # Budget check
            if estimated_cost_monthly > policies.get("max_budget_monthly", 1000):
                return False, f"❌ **Budget Denied**: Server limit is ${policies['max_budget_monthly']}/month. Requested: ${estimated_cost_monthly:.2f}/month."
            
            # Resource type check
            allowed_types = policies.get("allowed_resource_types", PolicyEnforcer.DEFAULT_POLICIES["allowed_resource_types"])
            if resource_type not in allowed_types:
                return False, f"❌ **Resource Denied**: `{resource_type}` is not permitted in this server.\nAllowed: {', '.join(allowed_types)}"
            
            # Instance type check
            allowed_instances = policies.get("allowed_instance_types", PolicyEnforcer.DEFAULT_POLICIES["allowed_instance_types"])
            if instance_type not in allowed_instances:
                return False, f"❌ **Instance Type Denied**: `{instance_type}` is not permitted.\nAllowed: {', '.join(allowed_instances[:5])}"
            
            # Instance count check
            current_count = cloud_db.get_guild_resource_count(guild_id, resource_type)
            max_instances = policies.get("max_instances", 10)
            if current_count >= max_instances:
                return False, f"❌ **Instance Limit Reached**: Server allows {max_instances} {resource_type} resources. Current: {current_count}"
            
            # Disk size check
            max_disk = policies.get("max_disk_size_gb", 500)
            if disk_size_gb > max_disk:
                return False, f"❌ **Disk Size Denied**: Maximum {max_disk}GB allowed. Requested: {disk_size_gb}GB"
            
            return True, "✅ **Policy Check Passed**: All guild policies satisfied."
        
        except Exception as e:
            print(f"[PolicyEnforcer] Validation error: {e}")
            # Fail-safe: deny on error
            return False, f"⚠️ **Policy Check Failed**: {str(e)}"
    
    @staticmethod
    def get_policy_summary(guild_id: str) -> str:
        """Get formatted summary of guild policies"""
        try:
            import cloud_database as cloud_db
            
            policies = cloud_db.get_guild_policies(guild_id)
            if not policies:
                policies = PolicyEnforcer.DEFAULT_POLICIES
            
            summary = f"""
**Server Cloud Policies**

💰 **Budget**: ${policies.get('max_budget_monthly', 1000)}/month max
📊 **Instance Limit**: {policies.get('max_instances', 10)} resources
🖥️ **Allowed Types**: {', '.join(policies.get('allowed_resource_types', [])[:5])}
💾 **Max Disk**: {policies.get('max_disk_size_gb', 500)}GB
✅ **Approval**: {'Required' if policies.get('require_approval', False) else 'Not Required'}
"""
            return summary
        
        except Exception as e:
            return f"Error getting policies: {e}"


class TerraformProgressTracker:
    """
    Parses Terraform/OpenTofu output to track deployment progress.
    Provides visual progress bar for Discord embeds.
    """
    
    def __init__(self):
        self.total_resources = 0
        self.completed_resources = 0
        self.current_action = "Initializing..."
        self.resource_patterns = [
            r"^(.*): Creating...",
            r"^(.*): Modifying...",
            r"^(.*): Destroying...",
            r"^(.*): Creation complete",
            r"^(.*): Modifications complete",
            r"^(.*): Destruction complete"
        ]
    
    def parse_plan_output(self, plan_output: str) -> int:
        """
        Parse 'terraform plan' output to count total resources.
        
        Returns:
            Total number of resources to be changed
        """
        try:
            # Look for: "Plan: X to add, Y to change, Z to destroy"
            match = re.search(r"Plan: (\d+) to add, (\d+) to change, (\d+) to destroy", plan_output)
            if match:
                add_count = int(match.group(1))
                change_count = int(match.group(2))
                destroy_count = int(match.group(3))
                self.total_resources = add_count + change_count + destroy_count
                return self.total_resources
            return 0
        
        except Exception as e:
            print(f"[ProgressTracker] Error parsing plan: {e}")
            return 0
    
    def update_from_line(self, line: str) -> bool:
        """
        Update progress from a single terraform output line.
        
        Returns:
            bool: True if progress was updated
        """
        try:
            for pattern in self.resource_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    resource_name = match.group(1)
                    
                    # Check if it's a completion action
                    if "complete" in line.lower():
                        self.completed_resources += 1
                    
                    # Update current action
                    if "Creating" in line:
                        self.current_action = f"Creating {resource_name}..."
                    elif "Modifying" in line:
                        self.current_action = f"Modifying {resource_name}..."
                    elif "Destroying" in line:
                        self.current_action = f"Destroying {resource_name}..."
                    
                    return True
            
            return False
        
        except Exception as e:
            print(f"[ProgressTracker] Error updating from line: {e}")
            return False
    
    def get_progress_percentage(self) -> float:
        """Calculate progress percentage (0-100)"""
        if self.total_resources == 0:
            return 0.0
        return min(100.0, (self.completed_resources / self.total_resources) * 100)
    
    def get_progress_bar(self, width: int = 10) -> str:
        """
        Generate visual progress bar.
        
        Args:
            width: Width of progress bar in characters
        
        Returns:
            Progress bar string like: [▓▓▓▓░░░░░░] 40%
        """
        percentage = self.get_progress_percentage()
        filled = int((percentage / 100) * width)
        empty = width - filled
        
        bar = "▓" * filled + "░" * empty
        return f"[{bar}] {percentage:.0f}%"
    
    def get_status_message(self) -> str:
        """Get formatted status message for Discord embed"""
        progress_bar = self.get_progress_bar()
        return f"{progress_bar}\n{self.current_action}\n({self.completed_resources}/{self.total_resources} resources)"


class IACEngineManager:
    """
    Abstract execution layer for terraform/tofu commands.
    Supports dynamic engine selection per guild.
    Includes real-time progress tracking.
    """
    
    SUPPORTED_ENGINES = ["terraform", "tofu"]
    
    @staticmethod
    async def execute_iac(
        guild_id: str,
        command_type: str,
        work_dir: str,
        engine: Optional[str] = None,
        progress_callback = None,
        session_id: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Execute IaC command with guild's preferred engine.
        Now supports real-time progress tracking via callback.
        
        Args:
            guild_id: Discord guild ID
            command_type: Command (plan, apply, destroy, validate)
            work_dir: Working directory for terraform files
            engine: Override engine (terraform/tofu), otherwise uses guild preference
            progress_callback: Async function to call with progress updates
            session_id: Vault session ID (for service account retrieval)
        
        Returns:
            (success: bool, stdout: str, stderr: str)
        """
        try:
            import asyncio
            import cloud_database as cloud_db
            
            # Get engine preference (default: terraform)
            if not engine:
                engine = cloud_db.get_engine_preference(guild_id) or "terraform"
            
            # Validate engine
            if engine not in IACEngineManager.SUPPORTED_ENGINES:
                return False, "", f"Unsupported engine: {engine}"
            
            # Set up service account credentials if session_id provided
            env = os.environ.copy()
            temp_creds_file = None
            
            if session_id:
                from cloud_security import ephemeral_vault
                sa_json = ephemeral_vault.get_service_account(session_id)
                
                if sa_json:
                    # Write to temporary file: /tmp/{guild_id}_creds.json
                    import tempfile
                    temp_creds_file = f"/tmp/{guild_id}_creds.json"
                    
                    with open(temp_creds_file, 'w') as f:
                        f.write(sa_json)
                    
                    # Set environment variable
                    env['GOOGLE_APPLICATION_CREDENTIALS'] = temp_creds_file
                    env['AWS_SHARED_CREDENTIALS_FILE'] = temp_creds_file  # For AWS
                    env['AZURE_CREDENTIALS_FILE'] = temp_creds_file  # For Azure
            
            # Build command
            cmd = f"{engine} {command_type} -no-color"
            
            # Add flags based on command type
            if command_type == "apply":
                cmd += " -auto-approve"
            elif command_type == "plan":
                cmd += " -out=tfplan"
            
            # Execute with streaming output
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Stream output with progress tracking
            stdout_lines = []
            stderr_lines = []
            tracker = TerraformProgressTracker()
            
            async def read_stream(stream, lines_list, is_stdout=True):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    
                    decoded_line = line.decode().strip()
                    lines_list.append(decoded_line)
                    
                    # Update progress tracker (only for stdout)
                    if is_stdout and progress_callback:
                        if tracker.update_from_line(decoded_line):
                            await progress_callback(tracker)
            
            # Read both streams concurrently
            await asyncio.gather(
                read_stream(process.stdout, stdout_lines, True),
                read_stream(process.stderr, stderr_lines, False)
            )
            
            await process.wait()
            
            # Cleanup temporary credentials file
            if temp_creds_file and os.path.exists(temp_creds_file):
                try:
                    os.remove(temp_creds_file)
                except Exception as e:
                    print(f"[IACEngine] Failed to remove temp creds: {e}")
            
            success = process.returncode == 0
            return success, "\n".join(stdout_lines), "\n".join(stderr_lines)
        
        except Exception as e:
            return False, "", f"Execution error: {str(e)}"
    
    @staticmethod
    def get_available_engines() -> list:
        """Check which IaC engines are installed"""
        import shutil
        
        available = []
        for engine in IACEngineManager.SUPPORTED_ENGINES:
            if shutil.which(engine):
                available.append(engine)
        
        return available


# Global ephemeral vault instance
ephemeral_vault = EphemeralVault()
