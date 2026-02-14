"""
Session State Objects - Clean Data Classes

This replaces passing dictionaries and individual arguments everywhere.
Similar to how D&D has Character sheets, Cloud has Session state.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime, timedelta
import time


class DeploymentState(Enum):
    """Deployment lifecycle states"""
    DRAFT = "draft"              # Just created
    VALIDATING = "validating"    # Running validation
    PLANNING = "planning"        # Running terraform plan
    PLAN_READY = "plan_ready"    # Plan complete, awaiting approval
    APPROVED = "approved"        # User approved
    APPLYING = "applying"        # Running terraform apply
    APPLIED = "applied"          # Successfully deployed
    FAILED = "failed"            # Deployment failed
    CANCELLED = "cancelled"      # User cancelled
    EXPIRED = "expired"          # Session timeout


@dataclass
class PlanResult:
    """Terraform plan result"""
    success: bool
    resources_to_add: int = 0
    resources_to_change: int = 0
    resources_to_destroy: int = 0
    plan_output: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    estimated_cost_hourly: float = 0.0
    
    @property
    def has_changes(self) -> bool:
        """Check if plan has any changes"""
        return (self.resources_to_add > 0 or 
                self.resources_to_change > 0 or 
                self.resources_to_destroy > 0)
    
    @property
    def summary(self) -> str:
        """Get plan summary text"""
        if not self.success:
            return "❌ Plan failed"
        
        if not self.has_changes:
            return "✅ No changes needed"
        
        return (f"Plan: +{self.resources_to_add} "
                f"~{self.resources_to_change} "
                f"-{self.resources_to_destroy}")
    
    @property
    def monthly_cost(self) -> float:
        """Estimated monthly cost"""
        return self.estimated_cost_hourly * 24 * 30


@dataclass
class CloudResource:
    """Individual resource to deploy"""
    type: str  # vm, database, bucket, etc.
    name: str
    config: Dict
    provider: str = "gcp"
    region: str = "us-central1"
    zone: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'type': self.type,
            'name': self.name,
            'config': self.config,
            'provider': self.provider,
            'region': self.region,
            'zone': self.zone
        }


@dataclass
class CloudSession:
    """
    Main session state object
    
    This is the "Character Sheet" for cloud deployments.
    All methods operate on this immutable state.
    """
    # Identity
    id: str
    project_id: str
    owner_id: int
    guild_id: int
    channel_id: int
    
    # Provider info
    provider: str  # gcp, aws, azure
    region: str
    
    # Resources
    resources: List[CloudResource] = field(default_factory=list)
    
    # State
    state: DeploymentState = DeploymentState.DRAFT
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 1800)  # 30 min
    
    # Plan result (populated after terraform plan)
    plan_result: Optional[PlanResult] = None
    
    # Validation result
    validation_result: Optional[Dict] = None
    
    # Metadata
    deployment_type: str = "single"  # single, batch, template
    thread_id: Optional[int] = None  # Discord thread for output
    
    # Terraform state
    terraform_output_dir: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return time.time() > self.expires_at
    
    @property
    def is_locked(self) -> bool:
        """Check if session is locked (can't be modified)"""
        return self.state in [
            DeploymentState.PLANNING,
            DeploymentState.APPLYING,
            DeploymentState.APPLIED
        ]
    
    @property
    def can_approve(self) -> bool:
        """Check if session can be approved"""
        return (self.state == DeploymentState.PLAN_READY and 
                self.plan_result and 
                self.plan_result.success)
    
    @property
    def time_remaining_seconds(self) -> int:
        """Get remaining time in seconds"""
        return max(0, int(self.expires_at - time.time()))
    
    @property
    def time_remaining_minutes(self) -> int:
        """Get remaining time in minutes"""
        return self.time_remaining_seconds // 60
    
    @property
    def resource_count(self) -> int:
        """Total number of resources"""
        return len(self.resources)
    
    def add_resource(self, resource: CloudResource):
        """Add a resource to the session"""
        if self.is_locked:
            raise ValueError(f"Cannot add resources in state: {self.state}")
        self.resources.append(resource)
        self.updated_at = time.time()
    
    def update_state(self, new_state: DeploymentState):
        """Update session state"""
        self.state = new_state
        self.updated_at = time.time()
    
    def set_plan_result(self, plan_result: PlanResult):
        """Set terraform plan result"""
        self.plan_result = plan_result
        self.updated_at = time.time()
        
        if plan_result.success:
            self.state = DeploymentState.PLAN_READY
        else:
            self.state = DeploymentState.FAILED
    
    def set_validation_result(self, validation: Dict):
        """Set validation result"""
        self.validation_result = validation
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'session_id': self.id,
            'project_id': self.project_id,
            'owner_id': str(self.owner_id),
            'guild_id': str(self.guild_id),
            'channel_id': str(self.channel_id),
            'provider': self.provider,
            'region': self.region,
            'resources': [r.to_dict() for r in self.resources],
            'state': self.state.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'expires_at': self.expires_at,
            'deployment_type': self.deployment_type,
            'thread_id': self.thread_id,
            'terraform_output_dir': self.terraform_output_dir
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CloudSession':
        """Create session from dictionary"""
        resources = [
            CloudResource(**r) for r in data.get('resources', [])
        ]
        
        return cls(
            id=data['session_id'],
            project_id=data['project_id'],
            owner_id=int(data['owner_id']),
            guild_id=int(data['guild_id']),
            channel_id=int(data['channel_id']),
            provider=data['provider'],
            region=data['region'],
            resources=resources,
            state=DeploymentState(data.get('state', 'draft')),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            expires_at=data.get('expires_at', time.time() + 1800),
            deployment_type=data.get('deployment_type', 'single'),
            thread_id=data.get('thread_id'),
            terraform_output_dir=data.get('terraform_output_dir')
        )
