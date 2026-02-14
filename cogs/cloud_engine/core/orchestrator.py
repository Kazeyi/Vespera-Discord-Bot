"""
Cloud Orchestrator - The "Brain" of the cloud provisioning system

This service layer coordinates all business logic:
- Session lifecycle management
- Validation coordination
- Terraform execution orchestration
- Database interaction

Think of this as the CloudSessionManager equivalent to the D&D system's CombatOrchestrator.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..models.session import CloudSession, DeploymentState, CloudResource, PlanResult
import cloud_database as db  # Use functional API
from infrastructure_policy_validator import InfrastructurePolicyValidator
from cloud_provisioning_generator import GCPGenerator, AWSGenerator, AzureGenerator
from .terraform_runner import TerraformRunner
from .cost_estimator import CostEstimator
from .git_manager import GitManager


class CloudOrchestrator:
    """
    Orchestrates cloud infrastructure provisioning lifecycle
    
    This is the central service layer that separates UI from business logic.
    All Discord commands should call this orchestrator instead of directly
    accessing database/validator/generator.
    """
    
    def __init__(self, guild_id: str = None):
        self.guild_id = guild_id
        self.cost_estimator = CostEstimator()
        self.git_manager = GitManager()
        
        # Generator mapping
        self.generators = {
            'gcp': GCPGenerator(),
            'aws': AWSGenerator(),
            'azure': AzureGenerator()
        }
        
        # Active sessions cache (session_id → CloudSession)
        self._sessions: Dict[str, CloudSession] = {}
    
    async def start_session(
        self,
        user_id: int,
        project_id: str,
        provider: str = 'gcp',
        ttl_minutes: int = 30
    ) -> CloudSession:
        """
        Start a new deployment session
        
        Args:
            user_id: Discord user ID
            project_id: Cloud project identifier
            provider: gcp/aws/azure
            ttl_minutes: Session expiry time
        
        Returns:
            CloudSession in DRAFT state
        """
        # Create session in database
        session_id = db.create_deployment_session(
            project_id=project_id,
            user_id=user_id,
            ttl_minutes=ttl_minutes
        )
        
        # Create CloudSession object
        session = CloudSession(
            id=session_id,
            project_id=project_id,
            user_id=user_id,
            provider=provider,
            resources=[],
            state=DeploymentState.DRAFT,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=ttl_minutes)
        )
        
        # Cache session
        self._sessions[session_id] = session
        
        # Audit log
        db.log_audit_event(
            event_type='session_created',
            user_id=str(user_id),
            guild_id=self.guild_id or 'unknown',
            action='create_deployment_session',
            project_id=project_id,
            session_id=session_id,
            details={'provider': provider, 'ttl_minutes': ttl_minutes}
        )
        
        # Initialize Git repo for project
        await self.git_manager.init_repo(project_id)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[CloudSession]:
        """
        Retrieve a session by ID
        
        Returns: CloudSession or None if not found/expired
        """
        # Check cache first
        if session_id in self._sessions:
            session = self._sessions[session_id]
            
            if session.is_expired:
                del self._sessions[session_id]
                return None
            
            return session
        
        # Fallback to database
        db_session = db.get_deployment_session(session_id)
        
        if not db_session:
            return None
        
        # Reconstruct CloudSession from database
        session = CloudSession.from_dict(db_session)
        
        if session.is_expired:
            return None
        
        # Cache it
        self._sessions[session_id] = session
        
        return session
    
    def add_resource(
        self,
        session_id: str,
        resource_type: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Add a resource to a session
        
        Args:
            session_id: Session ID
            resource_type: compute_vm, database, vpc, etc.
            config: Resource configuration dict
        
        Returns: True if added successfully
        """
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        if session.state not in [DeploymentState.DRAFT, DeploymentState.VALIDATING]:
            return False  # Can't modify locked sessions
        
        # Create resource
        resource = CloudResource(
            type=resource_type,
            config=config,
            provider=session.provider
        )
        
        # Add to session
        session.add_resource(resource)
        
        # Save to database
        db.add_session_resource(
            session_id=session_id,
            resource_type=resource_type,
            resource_config=config
        )
        
        return True
    
    async def validate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Run policy validation on a session
        
        This is the InfrastructurePolicyValidator equivalent to D&D's ActionEconomyValidator
        
        Returns: Validation result dict with is_valid, violations, quota_info
        """
        session = self.get_session(session_id)
        
        if not session:
            return {
                'is_valid': False,
                'violations': ['Session not found or expired']
            }
        
        # Update state
        session.update_state(DeploymentState.VALIDATING)
        
        # Run validator
        result = self.validator.validate_deployment(
            user_id=session.user_id,
            project_id=session.project_id,
            resources=[r.to_dict() for r in session.resources]
        )
        
        # Update session state based on result
        if result['is_valid']:
            session.update_state(DeploymentState.DRAFT)  # Ready for planning
        else:
            session.update_state(DeploymentState.FAILED)
        
        return result
    
    async def run_plan(self, session_id: str) -> PlanResult:
        """
        Execute terraform plan (Plan-First architecture)
        
        This is the critical workflow improvement:
        1. Generate terraform files
        2. Run terraform plan
        3. Parse plan output
        4. Estimate costs
        5. Store plan result
        6. Update session to PLAN_READY
        
        Returns: PlanResult with resources to add/change/destroy + cost estimate
        """
        session = self.get_session(session_id)
        
        if not session:
            return PlanResult(
                success=False,
                errors=['Session not found']
            )
        
        # Check if session can be planned
        if session.state not in [DeploymentState.DRAFT, DeploymentState.VALIDATING]:
            return PlanResult(
                success=False,
                errors=[f'Cannot plan session in state: {session.state.value}']
            )
        
        # Update state
        session.update_state(DeploymentState.PLANNING)
        
        try:
            # 1. Generate terraform files
            terraform_dir = await self._generate_terraform_files(session)
            
            # 2. Create terraform runner
            runner = TerraformRunner(terraform_dir)
            
            # 3. Run terraform plan
            plan_result = await runner.plan()
            
            # 4. Estimate costs using enhanced cost estimator
            if plan_result.success:
                cost_estimate = self.cost_estimator.estimate_deployment(
                    session.provider,
                    [{'type': r.type, 'config': r.config} for r in session.resources]
                )
                
                plan_result.estimated_cost_hourly = cost_estimate.hourly_cost
                plan_result.warnings.extend(cost_estimate.recommendations)
            
            # 5. Store plan result
            session.set_plan_result(plan_result)
            
            # 6. Update state
            if plan_result.success:
                session.update_state(DeploymentState.PLAN_READY)
                
                # Audit log
                db.log_audit_event(
                    event_type='plan_completed',
                    user_id=str(session.user_id),
                    guild_id=self.guild_id or 'unknown',
                    action='terraform_plan',
                    project_id=session.project_id,
                    session_id=session_id,
                    details={
                        'resources_to_add': plan_result.resources_to_add,
                        'resources_to_change': plan_result.resources_to_change,
                        'resources_to_destroy': plan_result.resources_to_destroy,
                        'estimated_monthly_cost': plan_result.monthly_cost
                    }
                )
            else:
                session.update_state(DeploymentState.FAILED)
                
                # Audit log failure
                db.log_audit_event(
                    event_type='plan_failed',
                    user_id=str(session.user_id),
                    guild_id=self.guild_id or 'unknown',
                    action='terraform_plan',
                    project_id=session.project_id,
                    session_id=session_id,
                    status='failure',
                    error_message='; '.join(plan_result.errors),
                    details={'errors': plan_result.errors}
                )
            
            return plan_result
        
        except Exception as e:
            session.update_state(DeploymentState.FAILED)
            
            # Audit log exception
            db.log_audit_event(
                event_type='plan_error',
                user_id=str(session.user_id),
                guild_id=self.guild_id or 'unknown',
                action='terraform_plan',
                project_id=session.project_id,
                session_id=session_id,
                status='failure',
                error_message=str(e)
            )
            
            return PlanResult(
                success=False,
                errors=[f'Plan execution failed: {str(e)}']
            )
    
    async def approve_and_apply(self, session_id: str, approver_id: int) -> bool:
        """
        Approve a plan and trigger terraform apply
        
        This is the "execute" step after plan approval.
        
        Args:
            session_id: Session ID
            approver_id: User who approved (for audit)
        
        Returns: True if apply started successfully
        """
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        # Check if session can be approved
        if not session.can_approve:
            return False
        
        # Update state
        session.approved_by = approver_id
        session.approved_at = datetime.now()
        session.update_state(DeploymentState.APPROVED)
        
        # Start apply in background
        asyncio.create_task(self._execute_apply(session_id))
        
        return True
    
    async def _execute_apply(self, session_id: str):
        """
        Background task to execute terraform apply
        
        This runs the actual terraform apply and updates session state.
        Includes Git commit and terraform state tracking.
        """
        session = self.get_session(session_id)
        
        if not session:
            return
        
        # Update state
        session.update_state(DeploymentState.APPLYING)
        
        try:
            # Get terraform directory
            terraform_dir = f"terraform_runs/{session_id}"
            
            # Create runner
            runner = TerraformRunner(terraform_dir)
            
            # Run apply
            success, output = await runner.apply()
            
            # Update state
            if success:
                session.update_state(DeploymentState.APPLIED)
                
                # Commit terraform configuration to Git
                commit_result = await self.git_manager.commit_configuration(
                    project_id=session.project_id,
                    user_id=session.user_id,
                    message=f"Deploy {len(session.resources)} resources via session {session_id[:8]}",
                    files=None  # Commit all files
                )
                
                # Save terraform state to database
                # (In production, parse tfstate file from terraform_dir)
                tfstate_path = Path(terraform_dir) / 'terraform.tfstate'
                if tfstate_path.exists():
                    tfstate_json = tfstate_path.read_text()
                    db.save_terraform_state(
                        project_id=session.project_id,
                        session_id=session_id,
                        tfstate_json=tfstate_json,
                        terraform_version='1.0'
                    )
                
                # Record in history
                db.record_deployment_history(
                    project_id=session.project_id,
                    user_id=session.user_id,
                    action='apply',
                    resources=len(session.resources),
                    success=True
                )
                
                # Audit log success
                db.log_audit_event(
                    event_type='deployment_completed',
                    user_id=str(session.user_id),
                    guild_id=self.guild_id or 'unknown',
                    action='terraform_apply',
                    project_id=session.project_id,
                    session_id=session_id,
                    details={
                        'resources_deployed': len(session.resources),
                        'git_commit': commit_result.get('commit_hash', 'unknown')[:8]
                    }
                )
            else:
                session.update_state(DeploymentState.FAILED)
                
                # Record failure
                db.record_deployment_history(
                    project_id=session.project_id,
                    user_id=session.user_id,
                    action='apply',
                    resources=len(session.resources),
                    success=False
                )
                
                # Audit log failure
                db.log_audit_event(
                    event_type='deployment_failed',
                    user_id=str(session.user_id),
                    guild_id=self.guild_id or 'unknown',
                    action='terraform_apply',
                    project_id=session.project_id,
                    session_id=session_id,
                    status='failure',
                    error_message=output[:500]  # First 500 chars of error
                )
        
        except Exception as e:
            session.update_state(DeploymentState.FAILED)
            
            # Audit log exception
            db.log_audit_event(
                event_type='deployment_error',
                user_id=str(session.user_id),
                guild_id=self.guild_id or 'unknown',
                action='terraform_apply',
                project_id=session.project_id,
                session_id=session_id,
                status='failure',
                error_message=str(e)
            )
            
            print(f"Apply failed for session {session_id}: {e}")
    
    async def cancel_session(self, session_id: str) -> bool:
        """
        Cancel an active session
        
        Returns: True if cancelled successfully
        """
        session = self.get_session(session_id)
        
        if not session:
            return False
        
        # Can only cancel if not already applying/applied
        if session.state in [DeploymentState.APPLYING, DeploymentState.APPLIED]:
            return False
        
        session.update_state(DeploymentState.CANCELLED)
        
        # Remove from cache
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        return True
    
    async def _generate_terraform_files(self, session: CloudSession) -> str:
        """
        Generate terraform .tf files for a session
        
        Returns: Path to terraform directory
        """
        # Create working directory
        terraform_dir = Path(f"terraform_runs/{session.id}")
        terraform_dir.mkdir(parents=True, exist_ok=True)
        
        # Get generator
        generator = self.generators.get(session.provider)
        
        if not generator:
            raise ValueError(f"Unknown provider: {session.provider}")
        
        # Generate terraform configuration
        tf_config = []
        
        for resource in session.resources:
            if resource.type == 'compute_vm':
                tf_config.append(generator.generate_vm(resource.config))
            elif resource.type == 'database':
                tf_config.append(generator.generate_database(resource.config))
            elif resource.type == 'vpc':
                tf_config.append(generator.generate_vpc(resource.config))
            # Add more resource types as needed
        
        # Write main.tf
        main_tf = terraform_dir / 'main.tf'
        main_tf.write_text('\n\n'.join(tf_config))
        
        return str(terraform_dir)
    
    def get_user_sessions(self, user_id: int, include_expired: bool = False) -> List[CloudSession]:
        """
        Get all sessions for a user
        
        Returns: List of CloudSession objects
        """
        # Get from database
        db_sessions = db.get_user_deployment_sessions(user_id)
        
        sessions = []
        
        for db_session in db_sessions:
            session = CloudSession.from_dict(db_session)
            
            if not include_expired and session.is_expired:
                continue
            
            sessions.append(session)
        
        return sessions
    
    def get_project_quota(self, project_id: str) -> Dict[str, Any]:
        """
        Get quota information for a project
        
        Returns: Dict with quota limits and usage
        """
        return db.get_project_quotas(project_id)
