"""
Cloud Guardrails System
Advanced safety, compliance, and budget guardrails for cloud recommendations
"""

from typing import Dict, List, Optional
import re


class CloudGuardrails:
    """Advanced guardrails for cloud recommendations"""
    
    # Budget limits in USD per month
    BUDGET_LIMITS = {
        'low': 100,
        'medium': 1000,
        'high': 10000
    }
    
    # High-cost resource types
    HIGH_COST_RESOURCES = ['gpu', 'highmem', 'large_storage', 'enterprise_database']
    
    # Compliance requirements
    COMPLIANCE_REQUIREMENTS = {
        'hipaa': ['encryption_at_rest', 'encryption_in_transit', 'audit_logging', 'access_controls', 'backup'],
        'gdpr': ['data_residency', 'encryption', 'data_deletion', 'access_controls', 'audit_logging'],
        'pci_dss': ['network_isolation', 'encryption', 'firewall', 'access_controls', 'logging', 'monitoring'],
        'sox': ['audit_logging', 'access_controls', 'data_retention', 'change_management']
    }
    
    def __init__(self):
        self.violation_history = []
    
    def validate_context(self, context: Dict, knowledge: List[Dict]) -> Dict:
        """
        Validate user request against guardrails
        
        Returns:
            {
                'allowed': bool,
                'violations': List[str],
                'warnings': List[str],
                'alternatives': List[Dict]
            }
        """
        violations = []
        warnings = []
        
        # Budget guardrail
        budget_violations = self._check_budget_guardrail(context)
        violations.extend(budget_violations)
        
        # Security guardrail
        security_warnings = self._check_security_guardrail(context, knowledge)
        warnings.extend(security_warnings)
        
        # Compliance guardrails
        compliance_violations = self._check_compliance_guardrails(context, knowledge)
        violations.extend(compliance_violations)
        
        # Complexity guardrail for beginners
        complexity_warnings = self._check_complexity_guardrail(context, knowledge)
        warnings.extend(complexity_warnings)
        
        # Cost optimization warnings
        cost_warnings = self._check_cost_optimization(context, knowledge)
        warnings.extend(cost_warnings)
        
        return {
            "allowed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "alternatives": self._suggest_alternatives(violations, warnings, context) if violations or warnings else []
        }
    
    def filter_recommendation(self, recommendation: Dict, context: Dict) -> Dict:
        """Filter final recommendation through safety rails"""
        
        filtered_rec = recommendation.copy()
        
        # Cost ceiling enforcement
        if context.get('budget'):
            budget_limit = self.BUDGET_LIMITS.get(context['budget'], 1000)
            estimated_cost = self._extract_cost(recommendation)
            
            if estimated_cost > budget_limit:
                filtered_rec['warnings'] = filtered_rec.get('warnings', [])
                filtered_rec['warnings'].append(
                    f"⚠️ Estimated cost (${estimated_cost}/mo) exceeds {context['budget']} budget (${budget_limit}/mo)"
                )
                filtered_rec['recommendation'] = "Consider downgrading instance type or using spot instances"
        
        # Security enhancement
        if 'encryption' in context.get('security_requirements', []):
            filtered_rec['configuration'] = self._add_encryption_config(
                filtered_rec.get('configuration', {})
            )
        
        # Add compliance markers
        if context.get('compliance_requirements'):
            filtered_rec['compliance_notes'] = self._add_compliance_notes(
                filtered_rec, context['compliance_requirements']
            )
        
        return filtered_rec
    
    def _check_budget_guardrail(self, context: Dict) -> List[str]:
        """Check budget constraints"""
        violations = []
        
        budget = context.get('budget', 'medium')
        resource_type = context.get('resource_type', '')
        
        # Prevent high-cost resources with low budget
        if budget == 'low' and any(hc in resource_type.lower() for hc in self.HIGH_COST_RESOURCES):
            violations.append(
                f"High-cost resource type '{resource_type}' incompatible with 'low' budget constraint"
            )
        
        return violations
    
    def _check_security_guardrail(self, context: Dict, knowledge: List[Dict]) -> List[str]:
        """Check security requirements"""
        warnings = []
        
        # Check if dealing with sensitive data
        use_case = context.get('use_case', '').lower()
        sensitive_keywords = ['pii', 'personal', 'healthcare', 'financial', 'payment', 'patient']
        
        has_sensitive_data = any(kw in use_case for kw in sensitive_keywords)
        has_encryption = 'encryption' in context.get('security_requirements', [])
        
        if has_sensitive_data and not has_encryption:
            warnings.append(
                "⚠️ Sensitive data detected in use case but encryption not explicitly requested. Strongly recommended."
            )
        
        # Check VPC requirement for production
        if context.get('environment') == 'production' and 'vpc' not in str(context).lower():
            warnings.append(
                "⚠️ Production environment detected. Consider using VPC/VNET for network isolation."
            )
        
        return warnings
    
    def _check_compliance_guardrails(self, context: Dict, knowledge: List[Dict]) -> List[str]:
        """Check compliance requirements"""
        violations = []
        
        compliance_frameworks = context.get('compliance_requirements', [])
        
        for framework in compliance_frameworks:
            if framework.lower() in self.COMPLIANCE_REQUIREMENTS:
                required_controls = self.COMPLIANCE_REQUIREMENTS[framework.lower()]
                framework_violations = self._validate_compliance_framework(
                    framework, required_controls, context, knowledge
                )
                violations.extend(framework_violations)
        
        return violations
    
    def _validate_compliance_framework(self, framework: str, required_controls: List[str], 
                                      context: Dict, knowledge: List[Dict]) -> List[str]:
        """Validate specific compliance framework requirements"""
        violations = []
        
        security_reqs = [req.lower() for req in context.get('security_requirements', [])]
        
        for control in required_controls:
            # Check if control is mentioned in security requirements or knowledge base
            control_mentioned = any(control.replace('_', ' ') in req for req in security_reqs)
            
            if not control_mentioned:
                # Check knowledge base
                kb_has_control = any(
                    control.replace('_', ' ') in doc.get('content', '').lower()
                    for doc in knowledge
                )
                
                if not kb_has_control:
                    violations.append(
                        f"{framework.upper()} compliance requires '{control.replace('_', ' ')}'"
                    )
        
        return violations
    
    def _check_complexity_guardrail(self, context: Dict, knowledge: List[Dict]) -> List[str]:
        """Check complexity vs expertise level"""
        warnings = []
        
        expertise = context.get('expertise_level', 'intermediate')
        
        if expertise == 'beginner':
            # Check if recommended solution is too complex
            high_complexity_docs = [
                doc for doc in knowledge 
                if doc.get('complexity_score', 3) > 4
            ]
            
            if high_complexity_docs:
                warnings.append(
                    f"⚠️ {len(high_complexity_docs)} complex configurations detected. "
                    "Consider using managed services or simplified architectures."
                )
        
        return warnings
    
    def _check_cost_optimization(self, context: Dict, knowledge: List[Dict]) -> List[str]:
        """Check for cost optimization opportunities"""
        warnings = []
        
        # Check for cost-saving opportunities in knowledge base
        cost_optimizations = [
            doc for doc in knowledge 
            if doc.get('category') == 'cost' and doc.get('cost_score', 3) < 2.5
        ]
        
        if cost_optimizations and context.get('budget') in ['low', 'medium']:
            warnings.append(
                f"💡 {len(cost_optimizations)} cost optimization opportunities found in knowledge base"
            )
        
        return warnings
    
    def _suggest_alternatives(self, violations: List[str], warnings: List[str], 
                            context: Dict) -> List[Dict]:
        """Suggest alternatives when guardrails are triggered"""
        alternatives = []
        
        # Budget alternatives
        if any("budget" in v.lower() for v in violations):
            alternatives.append({
                "suggestion": "Use spot/preemptible instances for non-critical workloads",
                "impact": "Cost reduction 50-70%",
                "tradeoff": "Potential interruption with 30-second notice"
            })
            alternatives.append({
                "suggestion": "Start with smaller instance type and scale up as needed",
                "impact": "Immediate cost savings, easy upgrade path",
                "tradeoff": "May need manual intervention to scale"
            })
        
        # Security alternatives
        if any("security" in w.lower() or "encrypt" in w.lower() for w in warnings):
            alternatives.append({
                "suggestion": "Enable default encryption for all storage and databases",
                "impact": "Enhanced security posture with minimal performance impact",
                "tradeoff": "Slight increase in complexity (~5%)"
            })
            alternatives.append({
                "suggestion": "Use VPC/VNET with private subnets for sensitive resources",
                "impact": "Network-level isolation and security",
                "tradeoff": "Requires VPC setup and management"
            })
        
        # Complexity alternatives
        if any("complex" in w.lower() for w in warnings):
            alternatives.append({
                "suggestion": "Use fully managed services (e.g., Cloud Run, App Engine, Azure Container Apps)",
                "impact": "Reduced operational complexity by 60-80%",
                "tradeoff": "Less control, potential vendor lock-in"
            })
        
        return alternatives
    
    def _extract_cost(self, recommendation: Dict) -> float:
        """Extract estimated monthly cost from recommendation"""
        cost_str = recommendation.get('estimated_monthly_cost', '0')
        
        # Parse cost range like "$100-$500" or "$250"
        cost_match = re.search(r'\$(\d+)', str(cost_str))
        if cost_match:
            return float(cost_match.group(1))
        
        return 0.0
    
    def _add_encryption_config(self, config: Dict) -> Dict:
        """Add encryption configuration"""
        enhanced_config = config.copy()
        enhanced_config['encryption_at_rest'] = True
        enhanced_config['encryption_in_transit'] = True
        enhanced_config['encryption_key_management'] = 'cloud_kms'
        return enhanced_config
    
    def _add_compliance_notes(self, recommendation: Dict, frameworks: List[str]) -> List[str]:
        """Add compliance-specific notes to recommendation"""
        notes = []
        
        for framework in frameworks:
            if framework.lower() == 'hipaa':
                notes.append("HIPAA: Ensure BAA (Business Associate Agreement) with cloud provider")
                notes.append("HIPAA: Enable audit logging and retain for 6+ years")
            elif framework.lower() == 'gdpr':
                notes.append("GDPR: Verify data residency in EU/EEA regions")
                notes.append("GDPR: Implement data deletion mechanisms")
            elif framework.lower() == 'pci_dss':
                notes.append("PCI DSS: Isolate cardholder data environment (CDE)")
                notes.append("PCI DSS: Implement network segmentation and firewalls")
        
        return notes
