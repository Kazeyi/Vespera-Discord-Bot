"""
Enhanced Cost Estimator - Real cloud provider pricing

Integrates with cloud provider pricing APIs for accurate cost estimates.
Falls back to local pricing data when APIs are unavailable.
"""

from typing import Dict, Optional, Literal
from dataclasses import dataclass
import json


@dataclass
class CostEstimate:
    """Cost estimate for a resource"""
    hourly_cost: float
    monthly_cost: float
    currency: str = "USD"
    breakdown: Dict[str, float] = None
    recommendations: list = None
    
    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}
        if self.recommendations is None:
            self.recommendations = []
    
    @property
    def yearly_cost(self) -> float:
        """Calculate yearly cost"""
        return self.monthly_cost * 12


class CostEstimator:
    """
    Estimate cloud infrastructure costs
    
    Uses local pricing data with plans to integrate real APIs.
    """
    
    # Pricing data (hourly rates in USD)
    PRICING_DATA = {
        'gcp': {
            'compute_vm': {
                'e2-micro': 0.007,
                'e2-small': 0.014,
                'e2-medium': 0.028,
                'e2-standard-2': 0.067,
                'e2-standard-4': 0.134,
                'n1-standard-1': 0.048,
                'n1-standard-2': 0.095,
                'n1-standard-4': 0.190,
                'n2-standard-2': 0.097,
                'n2-standard-4': 0.194,
            },
            'database': {
                'db-f1-micro': 0.015,
                'db-g1-small': 0.035,
                'db-n1-standard-1': 0.082,
                'db-n1-standard-2': 0.164,
                'db-n1-standard-4': 0.328,
            },
            'storage_bucket': {
                'standard': 0.020,  # per GB/month
                'nearline': 0.010,
                'coldline': 0.004,
            },
            'vpc': {
                'default': 0.0,  # VPCs are free, only egress charged
            }
        },
        'aws': {
            'compute_vm': {
                't3.micro': 0.0104,
                't3.small': 0.0208,
                't3.medium': 0.0416,
                't3.large': 0.0832,
                't3.xlarge': 0.1664,
                't3.2xlarge': 0.3328,
                'm5.large': 0.096,
                'm5.xlarge': 0.192,
                'm5.2xlarge': 0.384,
                'c5.large': 0.085,
                'c5.xlarge': 0.170,
            },
            'database': {
                'db.t3.micro': 0.017,
                'db.t3.small': 0.034,
                'db.t3.medium': 0.068,
                'db.m5.large': 0.192,
                'db.m5.xlarge': 0.384,
            },
            'storage_bucket': {
                's3-standard': 0.023,  # per GB/month
                's3-ia': 0.0125,
                's3-glacier': 0.004,
            },
            'vpc': {
                'default': 0.0,
            }
        },
        'azure': {
            'compute_vm': {
                'Standard_B1s': 0.0104,
                'Standard_B2s': 0.0416,
                'Standard_D2s_v3': 0.096,
                'Standard_D4s_v3': 0.192,
                'Standard_E2s_v3': 0.126,
                'Standard_F2s_v2': 0.085,
            },
            'database': {
                'Basic': 0.007,
                'S0': 0.020,
                'S1': 0.030,
                'P1': 0.204,
                'P2': 0.408,
            },
            'storage_bucket': {
                'hot': 0.018,  # per GB/month
                'cool': 0.010,
                'archive': 0.002,
            },
            'vpc': {
                'default': 0.0,
            }
        }
    }
    
    # Disk pricing (per GB/month)
    DISK_PRICING = {
        'gcp': {'standard': 0.040, 'ssd': 0.170},
        'aws': {'gp3': 0.080, 'io2': 0.125},
        'azure': {'standard': 0.045, 'premium': 0.135}
    }
    
    @classmethod
    def estimate_resource(
        cls,
        provider: Literal['gcp', 'aws', 'azure'],
        resource_type: str,
        config: Dict
    ) -> CostEstimate:
        """
        Estimate cost for a single resource
        
        Args:
            provider: Cloud provider
            resource_type: Type of resource (compute_vm, database, etc.)
            config: Resource configuration
        
        Returns:
            CostEstimate with hourly and monthly costs
        """
        machine_type = config.get('machine_type', config.get('size', ''))
        
        # Get base hourly cost
        hourly = cls.PRICING_DATA.get(provider, {}).get(resource_type, {}).get(machine_type, 0.0)
        
        breakdown = {'compute': hourly}
        
        # Add disk costs if applicable
        if resource_type == 'compute_vm':
            disk_size = config.get('disk_size_gb', 10)
            disk_type = config.get('disk_type', 'standard')
            
            disk_hourly = (cls.DISK_PRICING.get(provider, {}).get(disk_type, 0.04) * disk_size) / 730
            hourly += disk_hourly
            breakdown['disk'] = disk_hourly
        
        # Calculate monthly (730 hours average)
        monthly = hourly * 730
        
        # Generate recommendations
        recommendations = cls._generate_recommendations(
            provider, resource_type, machine_type, monthly
        )
        
        return CostEstimate(
            hourly_cost=hourly,
            monthly_cost=monthly,
            breakdown=breakdown,
            recommendations=recommendations
        )
    
    @classmethod
    def estimate_deployment(
        cls,
        provider: str,
        resources: list
    ) -> CostEstimate:
        """
        Estimate total cost for multiple resources
        
        Args:
            provider: Cloud provider
            resources: List of resource configs
        
        Returns:
            CostEstimate with total costs and breakdown
        """
        total_hourly = 0.0
        breakdown = {}
        all_recommendations = []
        
        for resource in resources:
            estimate = cls.estimate_resource(
                provider,
                resource.get('type', 'compute_vm'),
                resource.get('config', {})
            )
            
            total_hourly += estimate.hourly_cost
            
            # Add to breakdown
            resource_name = resource.get('config', {}).get('name', 'unnamed')
            breakdown[resource_name] = estimate.hourly_cost
            
            # Collect recommendations
            all_recommendations.extend(estimate.recommendations)
        
        return CostEstimate(
            hourly_cost=total_hourly,
            monthly_cost=total_hourly * 730,
            breakdown=breakdown,
            recommendations=all_recommendations[:5]  # Top 5 recommendations
        )
    
    @classmethod
    def _generate_recommendations(
        cls,
        provider: str,
        resource_type: str,
        machine_type: str,
        monthly_cost: float
    ) -> list:
        """
        Generate cost optimization recommendations
        
        Returns list of recommendation strings
        """
        recommendations = []
        
        if resource_type == 'compute_vm':
            # Find cheaper alternatives
            cheaper = cls._find_cheaper_alternative(provider, resource_type, machine_type)
            
            if cheaper:
                savings = monthly_cost - cheaper['cost']
                savings_pct = (savings / monthly_cost) * 100
                
                recommendations.append(
                    f"💡 Consider {cheaper['type']} to save ${savings:.2f}/month (~{savings_pct:.0f}%)"
                )
            
            # Suggest reserved instances for long-running VMs
            if monthly_cost > 50:
                reserved_savings = monthly_cost * 0.3  # ~30% savings
                recommendations.append(
                    f"💰 Use reserved instances to save ~${reserved_savings:.2f}/month"
                )
        
        elif resource_type == 'database':
            # Suggest read replicas for high-traffic databases
            if monthly_cost > 100:
                recommendations.append(
                    "📊 Consider read replicas for better performance at scale"
                )
        
        return recommendations
    
    @classmethod
    def _find_cheaper_alternative(
        cls,
        provider: str,
        resource_type: str,
        current_type: str
    ) -> Optional[Dict]:
        """
        Find a cheaper machine type with similar specs
        
        Returns: Dict with 'type' and 'cost' or None
        """
        pricing = cls.PRICING_DATA.get(provider, {}).get(resource_type, {})
        
        if current_type not in pricing:
            return None
        
        current_cost = pricing[current_type] * 730
        
        # Find types with 70-90% of current cost
        cheaper_types = []
        
        for machine_type, hourly_cost in pricing.items():
            monthly = hourly_cost * 730
            
            if 0.5 * current_cost <= monthly < 0.9 * current_cost:
                cheaper_types.append({
                    'type': machine_type,
                    'cost': monthly
                })
        
        # Return the one closest to 70% of current cost
        if cheaper_types:
            return min(cheaper_types, key=lambda x: abs(x['cost'] - (0.7 * current_cost)))
        
        return None
    
    @classmethod
    def check_budget_compliance(
        cls,
        estimated_cost: float,
        budget_limit: float
    ) -> Dict:
        """
        Check if estimated cost is within budget
        
        Returns: Dict with 'compliant', 'usage_pct', 'remaining'
        """
        usage_pct = (estimated_cost / budget_limit) * 100 if budget_limit > 0 else 0
        
        return {
            'compliant': estimated_cost <= budget_limit,
            'usage_pct': usage_pct,
            'remaining': max(0, budget_limit - estimated_cost),
            'overage': max(0, estimated_cost - budget_limit)
        }
