# --- Infrastructure Policy Validator ---
"""
InfrastructurePolicyValidator - Cloud Infrastructure Permission & Quota Validation
Inspired by ActionEconomyValidator from D&D system

D&D Analogy:
- ActionEconomyValidator checks if player has 1 Action available
- InfrastructurePolicyValidator checks if user can deploy db-n1-standard-1 in asia-southeast1

- D&D: extra_attacks logic (Fighter level 11 = 3 attacks)
- Cloud: quota_limits logic (Project has 10 VMs quota, 3 used = 7 available)
"""

import time
import re
from typing import Dict, List, Tuple, Optional
import cloud_database as cloud_db


class InfrastructurePolicyValidator:
    """
    Validate cloud infrastructure deployments against policies, quotas, and permissions.
    
    Similar to D&D Action Economy:
    - Users have deployment quotas (like action limits)
    - Policies define what can be deployed (like class abilities)
    - Quota overrides act like "Extra Attack" feature
    - Real-time validation prevents invalid deployments
    """
    
    # Resource type mappings
    RESOURCE_TYPES = {
        'vm': 'compute.instances',
        'instance': 'compute.instances',
        'compute': 'compute.instances',
        'database': 'database.instances',
        'db': 'database.instances',
        'bucket': 'storage.buckets',
        'storage': 'storage.buckets',
        'vpc': 'network.vpcs',
        'network': 'network.vpcs',
        'load_balancer': 'network.load_balancers',
        'lb': 'network.load_balancers',
        'k8s': 'compute.k8s_clusters',
        'kubernetes': 'compute.k8s_clusters',
    }
    
    # Machine size tiers (for quota calculations)
    MACHINE_SIZE_TIERS = {
        'micro': {'cpu': 1, 'ram': 1, 'tier': 'micro'},
        'small': {'cpu': 2, 'ram': 2, 'tier': 'small'},
        'medium': {'cpu': 4, 'ram': 8, 'tier': 'medium'},
        'large': {'cpu': 8, 'ram': 16, 'tier': 'large'},
        'xlarge': {'cpu': 16, 'ram': 32, 'tier': 'xlarge'},
    }
    
    # Estimated cost per hour (USD)
    COST_ESTIMATES = {
        'aws': {
            't3.micro': 0.0104, 't3.small': 0.0208, 't3.medium': 0.0416,
            't3.large': 0.0832, 't3.xlarge': 0.1664,
            'db.t3.micro': 0.017, 'db.t3.small': 0.034,
        },
        'gcp': {
            'e2-micro': 0.0084, 'e2-small': 0.0168, 'e2-medium': 0.0336,
            'e2-standard-2': 0.0672, 'e2-standard-4': 0.1344,
            'db-n1-standard-1': 0.095, 'db-n1-standard-2': 0.19,
        },
        'azure': {
            'Standard_B1s': 0.0104, 'Standard_B2s': 0.0416,
            'Standard_D2s_v3': 0.096, 'Standard_D4s_v3': 0.192,
        }
    }
    
    # Cache for policy validation
    _policy_cache = {}
    _cache_ttl = 300  # 5 minutes
    
    @staticmethod
    def validate_deployment(
        user_id: str,
        guild_id: str,
        project_id: str,
        provider: str,
        resource_type: str,
        resource_config: Dict,
        region: str
    ) -> Dict:
        """
        Main validation method - checks permissions, quotas, and policies
        
        Returns validation result similar to ActionEconomyValidator:
        {
            'is_valid': bool,
            'can_deploy': bool,
            'violations': [],
            'quota_info': {},
            'cost_estimate': float,
            'warning': str,
            'enforcement_instruction': str
        }
        """
        result = {
            'is_valid': True,
            'can_deploy': True,
            'violations': [],
            'quota_info': {},
            'cost_estimate': 0.0,
            'warning': '',
            'enforcement_instruction': '',
            'required_approvals': []
        }
        
        # 1. Check if user has permission (like checking if player has action available)
        permission_check = InfrastructurePolicyValidator._check_user_permission(
            user_id, guild_id, provider, resource_type, resource_config
        )
        
        if not permission_check['allowed']:
            result['is_valid'] = False
            result['can_deploy'] = False
            result['violations'].append(permission_check['reason'])
            result['warning'] = f"⛔ PERMISSION DENIED: {permission_check['reason']}"
            result['enforcement_instruction'] = (
                f"User @{user_id} does not have permission to deploy {resource_type}. "
                f"Required role: {permission_check.get('required_role', 'CloudAdmin')}"
            )
            return result
        
        # 2. Check quota limits (like checking Extra Attack feature)
        quota_check = InfrastructurePolicyValidator._check_quota_limits(
            project_id, resource_type, region, resource_config
        )
        
        result['quota_info'] = quota_check
        
        if not quota_check['quota_available']:
            result['is_valid'] = False
            result['can_deploy'] = False
            result['violations'].append(quota_check['reason'])
            result['warning'] = f"⚠️ QUOTA EXCEEDED: {quota_check['reason']}"
            result['enforcement_instruction'] = (
                f"Project {project_id} has exceeded quota for {resource_type}. "
                f"Current: {quota_check['used']}/{quota_check['limit']}. "
                f"Requested: {quota_check['requested']}. "
                f"Please delete existing resources or request quota increase."
            )
            return result
        
        # 3. Check infrastructure policies (like checking action economy rules)
        policy_check = InfrastructurePolicyValidator._check_infrastructure_policies(
            guild_id, provider, resource_type, resource_config, region
        )
        
        if not policy_check['compliant']:
            if policy_check.get('require_approval'):
                # Policy violation but can be approved (like DM discretion in D&D)
                result['required_approvals'].append({
                    'policy': policy_check['policy_name'],
                    'reason': policy_check['reason'],
                    'approver_role': 'CloudAdmin'
                })
                result['warning'] = f"⚠️ APPROVAL REQUIRED: {policy_check['reason']}"
            else:
                # Hard policy violation
                result['is_valid'] = False
                result['can_deploy'] = False
                result['violations'].append(policy_check['reason'])
                result['warning'] = f"⛔ POLICY VIOLATION: {policy_check['reason']}"
                result['enforcement_instruction'] = policy_check['enforcement_instruction']
                return result
        
        # 4. Estimate cost
        result['cost_estimate'] = InfrastructurePolicyValidator._estimate_cost(
            provider, resource_type, resource_config
        )
        
        # 5. Check cost limits
        if result['cost_estimate'] > 0:
            cost_check = InfrastructurePolicyValidator._check_cost_limit(
                project_id, result['cost_estimate'], policy_check.get('max_cost_per_hour', 100.0)
            )
            
            if not cost_check['within_budget']:
                result['is_valid'] = False
                result['can_deploy'] = False
                result['violations'].append(cost_check['reason'])
                result['warning'] = f"💰 BUDGET EXCEEDED: {cost_check['reason']}"
        
        # 6. Generate summary
        if result['is_valid'] and result['can_deploy']:
            if result['required_approvals']:
                result['warning'] = f"✅ Pre-approved (requires final approval from CloudAdmin)"
            else:
                result['warning'] = f"✅ Validation passed - Ready to deploy"
                result['enforcement_instruction'] = (
                    f"Deployment authorized: {resource_type} in {region}. "
                    f"Estimated cost: ${result['cost_estimate']:.4f}/hour. "
                    f"Quota: {quota_check['used']}/{quota_check['limit']} (will be {quota_check['used'] + quota_check['requested']}/{quota_check['limit']})"
                )
        
        return result
    
    @staticmethod
    def _check_user_permission(user_id: str, guild_id: str, provider: str, 
                                resource_type: str, resource_config: Dict) -> Dict:
        """Check if user has permission to deploy this resource type"""
        # Get user permissions from database
        perms = cloud_db.get_user_permissions(user_id, guild_id, provider)
        
        if not perms:
            return {
                'allowed': False,
                'reason': f'No cloud permissions assigned for {provider}',
                'required_role': 'CloudUser'
            }
        
        # Check resource-specific permissions
        resource_base = resource_type.split('.')[0] if '.' in resource_type else resource_type
        
        permission_map = {
            'compute': 'can_create_vm',
            'database': 'can_create_db',
            'k8s': 'can_create_k8s',
            'network': 'can_create_network',
            'storage': 'can_create_storage',
        }
        
        required_perm = permission_map.get(resource_base, 'can_create_vm')
        
        if not perms.get(required_perm, False):
            return {
                'allowed': False,
                'reason': f'User lacks {required_perm} permission',
                'required_role': perms.get('role_name', 'CloudAdmin')
            }
        
        # Check machine size restrictions (like Extra Attack limitations)
        if 'machine_type' in resource_config:
            max_size = perms.get('max_vm_size')
            if max_size and not InfrastructurePolicyValidator._is_size_allowed(
                resource_config['machine_type'], max_size
            ):
                return {
                    'allowed': False,
                    'reason': f'Machine type {resource_config["machine_type"]} exceeds max allowed size {max_size}',
                    'required_role': 'CloudAdmin'
                }
        
        # Check region restrictions
        allowed_regions = perms.get('allowed_regions')
        if allowed_regions:
            allowed_list = [r.strip() for r in allowed_regions.split(',')]
            if resource_config.get('region') not in allowed_list:
                return {
                    'allowed': False,
                    'reason': f'Region {resource_config.get("region")} not in allowed regions: {allowed_regions}',
                    'required_role': perms.get('role_name', 'CloudAdmin')
                }
        
        return {
            'allowed': True,
            'role': perms.get('role_name', 'CloudUser')
        }
    
    @staticmethod
    def _check_quota_limits(project_id: str, resource_type: str, region: str, 
                            resource_config: Dict) -> Dict:
        """
        Check quota limits (like Extra Attack checking)
        
        Returns quota information similar to D&D attack count validation
        """
        # Normalize resource type
        normalized_type = InfrastructurePolicyValidator.RESOURCE_TYPES.get(
            resource_type, resource_type
        )
        
        # Calculate how many "quota units" this resource consumes
        quota_consumption = 1  # Default: 1 resource = 1 quota unit
        
        # Check if we need CPU/RAM quota too
        additional_checks = []
        
        if 'machine_type' in resource_config:
            # Extract CPU/RAM from machine type
            cpu, ram = InfrastructurePolicyValidator._extract_machine_specs(
                resource_config['machine_type']
            )
            if cpu:
                additional_checks.append(('compute.cpus', region, cpu))
            if ram:
                additional_checks.append(('compute.ram_gb', region, ram))
        
        # Check main resource quota
        can_deploy, quota_info = cloud_db.check_quota(
            project_id, normalized_type, region, quota_consumption
        )
        
        if not can_deploy:
            return {
                'quota_available': False,
                'reason': quota_info.get('message', 'Quota limit exceeded'),
                'limit': quota_info.get('quota_limit', 0),
                'used': quota_info.get('quota_used', 0),
                'requested': quota_consumption,
                'available': quota_info.get('available', 0)
            }
        
        # Check additional quotas (CPU/RAM)
        for check_type, check_region, check_amount in additional_checks:
            can_deploy_additional, additional_info = cloud_db.check_quota(
                project_id, check_type, check_region, check_amount
            )
            
            if not can_deploy_additional:
                return {
                    'quota_available': False,
                    'reason': f'Insufficient {check_type} quota: {additional_info.get("message")}',
                    'limit': additional_info.get('quota_limit', 0),
                    'used': additional_info.get('quota_used', 0),
                    'requested': check_amount,
                    'available': additional_info.get('available', 0)
                }
        
        return {
            'quota_available': True,
            'limit': quota_info.get('quota_limit', 0),
            'used': quota_info.get('quota_used', 0),
            'requested': quota_consumption,
            'available': quota_info.get('available', 0)
        }
    
    @staticmethod
    def _check_infrastructure_policies(guild_id: str, provider: str, resource_type: str,
                                        resource_config: Dict, region: str) -> Dict:
        """Check if deployment complies with infrastructure policies"""
        # Get all active policies for guild
        policies = cloud_db.get_guild_policies(guild_id, is_active=True)
        
        for policy in policies:
            # Check if policy applies to this resource
            if not InfrastructurePolicyValidator._policy_matches_resource(
                policy, provider, resource_type, resource_config
            ):
                continue
            
            # Check policy type
            if policy['policy_type'] == 'region':
                # Region restriction policy
                if policy.get('allowed_values'):
                    allowed_regions = policy['allowed_values'].split(',')
                    if region not in allowed_regions:
                        return {
                            'compliant': False,
                            'policy_name': policy['policy_name'],
                            'reason': f'Region {region} not allowed by policy {policy["policy_name"]}',
                            'enforcement_instruction': f'Allowed regions: {policy["allowed_values"]}',
                            'require_approval': policy.get('require_approval', False)
                        }
            
            elif policy['policy_type'] == 'cost':
                # Cost limit policy
                max_cost = policy.get('max_cost_per_hour')
                if max_cost:
                    estimated_cost = InfrastructurePolicyValidator._estimate_cost(
                        provider, resource_type, resource_config
                    )
                    if estimated_cost > max_cost:
                        return {
                            'compliant': False,
                            'policy_name': policy['policy_name'],
                            'reason': f'Estimated cost ${estimated_cost:.4f}/hr exceeds policy limit ${max_cost:.4f}/hr',
                            'enforcement_instruction': f'Reduce resource size or request policy exception',
                            'require_approval': policy.get('require_approval', False)
                        }
            
            elif policy['policy_type'] == 'security':
                # Security policy checks
                if policy.get('denied_values'):
                    denied = policy['denied_values'].split(',')
                    machine_type = resource_config.get('machine_type', '')
                    if any(d.strip() in machine_type for d in denied):
                        return {
                            'compliant': False,
                            'policy_name': policy['policy_name'],
                            'reason': f'Machine type {machine_type} is denied by security policy',
                            'enforcement_instruction': 'Use approved machine types only',
                            'require_approval': policy.get('require_approval', False)
                        }
        
        return {
            'compliant': True,
            'max_cost_per_hour': 100.0  # Default max cost
        }
    
    @staticmethod
    def _policy_matches_resource(policy: Dict, provider: str, resource_type: str, 
                                  resource_config: Dict) -> bool:
        """Check if policy applies to this resource (pattern matching)"""
        pattern = policy['resource_pattern']
        
        # Simple pattern matching (can be enhanced with regex)
        if pattern == '*' or pattern == 'all':
            return True
        
        if pattern.startswith('provider:'):
            target_provider = pattern.split(':')[1]
            return provider == target_provider
        
        if pattern.startswith('type:'):
            target_type = pattern.split(':')[1]
            return resource_type.startswith(target_type)
        
        # Regex pattern matching
        try:
            return bool(re.match(pattern, f"{provider}.{resource_type}"))
        except:
            return False
    
    @staticmethod
    def _estimate_cost(provider: str, resource_type: str, resource_config: Dict) -> float:
        """Estimate hourly cost for resource"""
        machine_type = resource_config.get('machine_type', '')
        
        if not machine_type:
            return 0.0
        
        cost_table = InfrastructurePolicyValidator.COST_ESTIMATES.get(provider, {})
        
        # Exact match
        if machine_type in cost_table:
            return cost_table[machine_type]
        
        # Fuzzy match for similar types
        for cost_key, cost_value in cost_table.items():
            if cost_key.replace('.', '-') in machine_type or machine_type in cost_key:
                return cost_value
        
        # Default estimate based on size tier
        if 'micro' in machine_type.lower():
            return 0.01
        elif 'small' in machine_type.lower():
            return 0.02
        elif 'medium' in machine_type.lower():
            return 0.04
        elif 'large' in machine_type.lower():
            return 0.08
        elif 'xlarge' in machine_type.lower():
            return 0.16
        
        return 0.05  # Default fallback
    
    @staticmethod
    def _check_cost_limit(project_id: str, estimated_cost: float, max_cost_per_hour: float) -> Dict:
        """Check if deployment is within budget"""
        project = cloud_db.get_cloud_project(project_id)
        
        if not project:
            return {
                'within_budget': False,
                'reason': 'Project not found'
            }
        
        budget_limit = project.get('budget_limit', 1000.0)
        
        # Calculate current monthly cost from existing resources
        existing_resources = cloud_db.get_project_resources(project_id)
        current_hourly_cost = sum(r.get('cost_per_hour', 0) for r in existing_resources)
        
        # Estimate monthly cost (24 hours * 30 days)
        monthly_estimate = (current_hourly_cost + estimated_cost) * 24 * 30
        
        if monthly_estimate > budget_limit:
            return {
                'within_budget': False,
                'reason': f'Monthly cost estimate ${monthly_estimate:.2f} exceeds budget ${budget_limit:.2f}',
                'current_monthly': current_hourly_cost * 24 * 30,
                'new_monthly': monthly_estimate
            }
        
        if estimated_cost > max_cost_per_hour:
            return {
                'within_budget': False,
                'reason': f'Resource cost ${estimated_cost:.4f}/hr exceeds policy limit ${max_cost_per_hour:.4f}/hr'
            }
        
        return {
            'within_budget': True,
            'current_monthly': current_hourly_cost * 24 * 30,
            'new_monthly': monthly_estimate,
            'budget_remaining': budget_limit - monthly_estimate
        }
    
    @staticmethod
    def _extract_machine_specs(machine_type: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract CPU and RAM from machine type string"""
        # GCP pattern: e2-standard-4 = 4 vCPUs, 16 GB
        # AWS pattern: t3.xlarge = 4 vCPUs, 16 GB
        # Azure pattern: Standard_D4s_v3 = 4 vCPUs, 16 GB
        
        cpu_map = {
            'micro': (1, 1), 'small': (1, 2), 'medium': (2, 4),
            'large': (2, 8), 'xlarge': (4, 16), '2xlarge': (8, 32),
            'standard-1': (1, 4), 'standard-2': (2, 8), 'standard-4': (4, 16),
            'standard-8': (8, 32), 'standard-16': (16, 64),
        }
        
        machine_lower = machine_type.lower()
        
        for key, (cpu, ram) in cpu_map.items():
            if key in machine_lower:
                return cpu, ram
        
        # Try to extract number from machine type
        import re
        numbers = re.findall(r'\d+', machine_type)
        if numbers:
            num = int(numbers[-1])
            if num <= 32:
                return num, num * 4  # Estimate: 4GB per vCPU
        
        return None, None
    
    @staticmethod
    def _is_size_allowed(machine_type: str, max_allowed: str) -> bool:
        """Check if machine size is within allowed limit"""
        size_order = ['micro', 'small', 'medium', 'large', 'xlarge', '2xlarge', '4xlarge']
        
        def get_size_index(mtype: str) -> int:
            for idx, size in enumerate(size_order):
                if size in mtype.lower():
                    return idx
            return 999  # Unknown size = very large
        
        return get_size_index(machine_type) <= get_size_index(max_allowed)
    
    @staticmethod
    def validate_batch_deployment(user_id: str, guild_id: str, project_id: str,
                                   provider: str, resources: List[Dict]) -> Dict:
        """
        Validate multiple resources at once (like validating a full turn in D&D)
        
        Returns aggregated validation result for all resources
        """
        results = {
            'is_valid': True,
            'can_deploy_all': True,
            'resources': [],
            'total_cost_estimate': 0.0,
            'total_violations': [],
            'summary': ''
        }
        
        for resource in resources:
            validation = InfrastructurePolicyValidator.validate_deployment(
                user_id, guild_id, project_id, provider,
                resource['resource_type'],
                resource['config'],
                resource.get('region', 'us-central1')
            )
            
            results['resources'].append({
                'resource': resource,
                'validation': validation
            })
            
            results['total_cost_estimate'] += validation.get('cost_estimate', 0.0)
            
            if not validation['is_valid']:
                results['is_valid'] = False
                results['can_deploy_all'] = False
                results['total_violations'].extend(validation.get('violations', []))
        
        # Generate summary
        total_resources = len(resources)
        valid_resources = sum(1 for r in results['resources'] if r['validation']['is_valid'])
        
        if results['can_deploy_all']:
            results['summary'] = (
                f"✅ All {total_resources} resources validated successfully. "
                f"Total estimated cost: ${results['total_cost_estimate']:.4f}/hour"
            )
        else:
            results['summary'] = (
                f"⛔ Validation failed: {valid_resources}/{total_resources} resources are valid. "
                f"Violations: {len(results['total_violations'])}"
            )
        
        return results
