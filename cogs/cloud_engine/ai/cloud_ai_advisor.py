"""
Cloud AI Advisor
AI-powered cloud infrastructure recommendations using Groq/Gemini with Chain-of-Thought reasoning
"""

import os
import json
import asyncio
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

# Groq API
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Google Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .knowledge_rag import CloudKnowledgeRAG
from .guardrails import CloudGuardrails
try:
    from cogs.utility_core.personality import VesperaPersonality as VP
except ImportError:
    # Fallback/Mock if import fails (e.g. running standalone)
    class VP:
        SYSTEM_PROMPT = "You are Vespera, the Silent Architect. High-tier cloud intelligence."


class AIModel(Enum):
    """Available AI models for recommendations"""
    GROQ_LLAMA = "groq_llama"  # Groq with Llama 3
    GROQ_MIXTRAL = "groq_mixtral"  # Groq with Mixtral
    GEMINI_PRO = "gemini_pro"  # Google Gemini Pro
    GEMINI_FLASH = "gemini_flash"  # Google Gemini Flash (faster)


@dataclass
class RecommendationResult:
    """Result from AI recommendation"""
    recommendation: Optional[Dict]
    reasoning_chain: List[str]
    sources: List[str]
    confidence_score: float
    provider_comparison: Optional[Dict]
    warnings: List[str]
    violations: List[str]
    alternatives: List[Dict]


class CloudAIAdvisor:
    """AI-driven cloud infrastructure recommendations with Chain-of-Thought reasoning"""
    
    # Groq model configurations
    GROQ_MODELS = {
        AIModel.GROQ_LLAMA: "llama-3.3-70b-versatile",
        AIModel.GROQ_MIXTRAL: "mixtral-8x7b-32768"
    }
    
    # Gemini model configurations
    GEMINI_MODELS = {
        AIModel.GEMINI_PRO: "gemini-1.5-pro",
        AIModel.GEMINI_FLASH: "gemini-1.5-flash"
    }
    
    def __init__(self, rag_system: CloudKnowledgeRAG, groq_api_key: Optional[str] = None,
                 gemini_api_key: Optional[str] = None):
        """
        Initialize AI Advisor
        
        Args:
            rag_system: CloudKnowledgeRAG instance
            groq_api_key: Groq API key (or set GROQ_API_KEY env var)
            gemini_api_key: Google API key (or set GEMINI_API_KEY env var)
        """
        self.rag = rag_system
        self.guardrails = CloudGuardrails()
        
        # Initialize Groq client
        self.groq_client = None
        if GROQ_AVAILABLE:
            api_key = groq_api_key or os.getenv('GROQ_API_KEY')
            if api_key:
                self.groq_client = Groq(api_key=api_key)
        
        # Initialize Gemini client
        self.gemini_client = None
        if GEMINI_AVAILABLE:
            api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_client = True
    
    async def generate_recommendation(self, context: Dict, ai_model: AIModel = AIModel.GROQ_LLAMA,
                                     use_cot: bool = True) -> RecommendationResult:
        """
        Generate AI recommendation with Chain-of-Thought reasoning
        
        Args:
            context: {
                "provider": "aws/gcp/azure",
                "resource_type": "vm/database/kubernetes",
                "use_case": "web_app/batch_processing/data_lake",
                "budget": "low/medium/high",
                "security_requirements": ["encryption", "compliance"],
                "performance_needs": ["high_throughput", "low_latency"],
                "compliance_requirements": ["hipaa", "gdpr"],
                "expertise_level": "beginner/intermediate/expert",
                "environment": "development/staging/production"
            }
            ai_model: Which AI model to use (Groq or Gemini)
            use_cot: Whether to use Chain-of-Thought reasoning
            
        Returns:
            RecommendationResult with full recommendation and reasoning
        """
        
        # Step 1: Retrieve relevant knowledge
        retrieved_knowledge = self._retrieve_knowledge(context)
        
        # Step 2: Apply guardrails
        guardrail_check = self.guardrails.validate_context(context, retrieved_knowledge)
        
        if not guardrail_check["allowed"]:
            return RecommendationResult(
                recommendation=None,
                reasoning_chain=["Request blocked by guardrails"],
                sources=[],
                confidence_score=0.0,
                provider_comparison=None,
                warnings=guardrail_check["warnings"],
                violations=guardrail_check["violations"],
                alternatives=guardrail_check["alternatives"]
            )
        
        # Step 3: Generate reasoning chain
        reasoning_chain = self._build_reasoning_chain(context, retrieved_knowledge) if use_cot else []
        
        # Step 4: Generate recommendation using selected AI model
        try:
            if ai_model in [AIModel.GROQ_LLAMA, AIModel.GROQ_MIXTRAL]:
                recommendation = await self._generate_with_groq(context, reasoning_chain, retrieved_knowledge, ai_model)
            elif ai_model in [AIModel.GEMINI_PRO, AIModel.GEMINI_FLASH]:
                recommendation = await self._generate_with_gemini(context, reasoning_chain, retrieved_knowledge, ai_model)
            else:
                recommendation = self._generate_rule_based(context, reasoning_chain, retrieved_knowledge)
        except Exception as e:
            print(f"⚠️ AI generation failed: {e}, falling back to rule-based")
            recommendation = self._generate_rule_based(context, reasoning_chain, retrieved_knowledge)
        
        # Step 5: Apply final guardrails
        recommendation = self.guardrails.filter_recommendation(recommendation, context)
        
        # Step 6: Calculate confidence and provider comparison
        confidence = self._calculate_confidence(context, recommendation, retrieved_knowledge)
        provider_comp = self._compare_providers(context, retrieved_knowledge) if context.get("provider") == "any" else None
        
        return RecommendationResult(
            recommendation=recommendation,
            reasoning_chain=reasoning_chain,
            sources=[doc.get("source", "knowledge_base") for doc in retrieved_knowledge[:3]],
            confidence_score=confidence,
            provider_comparison=provider_comp,
            warnings=guardrail_check["warnings"] + recommendation.get('warnings', []),
            violations=guardrail_check["violations"],
            alternatives=recommendation.get('alternatives', [])
        )
    
    def _retrieve_knowledge(self, context: Dict) -> List[Dict]:
        """Retrieve relevant knowledge from RAG system"""
        provider = context.get('provider', None)
        if provider == 'any':
            provider = None
        
        # Build search query from context
        query_parts = [
            context.get('use_case', ''),
            context.get('resource_type', ''),
            ' '.join(context.get('performance_needs', [])),
            ' '.join(context.get('security_requirements', []))
        ]
        query = ' '.join(filter(None, query_parts))
        
        # Search knowledge base
        results = self.rag.hybrid_search(query, provider=provider, limit=10)
        
        # Also search for patterns
        patterns = self.rag.search_patterns(context.get('use_case', ''), provider)
        
        # Combine results
        all_knowledge = results + [{'type': 'pattern', **p} for p in patterns]
        
        return all_knowledge
    
    def _build_reasoning_chain(self, context: Dict, knowledge: List[Dict]) -> List[str]:
        """Build Chain-of-Thought reasoning steps"""
        chain = []
        
        # Step 1: Analyze requirements
        chain.append("🔍 Step 1 - Requirement Analysis:")
        chain.append(f"  • Use Case: {context.get('use_case', 'general')}")
        chain.append(f"  • Resource Type: {context.get('resource_type', 'unspecified')}")
        chain.append(f"  • Provider: {context.get('provider', 'any')}")
        chain.append(f"  • Budget: {context.get('budget', 'medium')}")
        chain.append(f"  • Environment: {context.get('environment', 'development')}")
        
        # Step 2: Evaluate constraints
        chain.append("\n⚙️ Step 2 - Constraints Identified:")
        constraints = []
        
        if context.get('budget') == 'low':
            constraints.append("Cost optimization is critical")
        if 'encryption' in context.get('security_requirements', []):
            constraints.append("Data encryption at rest and in transit required")
        if context.get('compliance_requirements'):
            constraints.append(f"Compliance: {', '.join(context['compliance_requirements'])}")
        if context.get('performance_needs'):
            constraints.append(f"Performance: {', '.join(context['performance_needs'])}")
        
        if constraints:
            chain.extend([f"  • {c}" for c in constraints])
        else:
            chain.append("  • No strict constraints specified")
        
        # Step 3: Match with best practices
        chain.append("\n📚 Step 3 - Best Practice Matching:")
        relevant_docs = [doc for doc in knowledge if doc.get('impact_score', 0) > 50][:3]
        
        if relevant_docs:
            for i, doc in enumerate(relevant_docs, 1):
                service = doc.get('service', 'Unknown')
                content_preview = doc.get('content', '')[:80].replace('\n', ' ')
                chain.append(f"  {i}. {service}: {content_preview}...")
        else:
            chain.append("  • Using general best practices")
        
        # Step 4: Consider trade-offs
        chain.append("\n⚖️ Step 4 - Trade-off Analysis:")
        trade_offs = self._calculate_trade_offs(context, knowledge)
        for dimension, score in trade_offs.items():
            chain.append(f"  • {dimension}: {'⭐' * int(score)}{' ☆' * (5 - int(score))} ({score}/5)")
        
        return chain
    
    def _calculate_trade_offs(self, context: Dict, knowledge: List[Dict]) -> Dict[str, float]:
        """Calculate trade-off matrix for different dimensions"""
        # Average scores from knowledge base
        avg_cost = sum(doc.get('cost_score', 3) for doc in knowledge) / len(knowledge) if knowledge else 3.0
        avg_complexity = sum(doc.get('complexity_score', 3) for doc in knowledge) / len(knowledge) if knowledge else 3.0
        avg_security = sum(doc.get('security_score', 3) for doc in knowledge) / len(knowledge) if knowledge else 3.0
        
        # Adjust based on context
        if context.get('budget') == 'low':
            avg_cost = min(5.0, avg_cost + 1.0)  # Cost concern increases
        if context.get('expertise_level') == 'beginner':
            avg_complexity = max(1.0, avg_complexity - 1.0)  # Prefer simpler solutions
        if context.get('security_requirements'):
            avg_security = min(5.0, avg_security + 0.5)
        
        return {
            'Cost Efficiency': round(6.0 - avg_cost, 1),  # Invert so higher is better
            'Simplicity': round(6.0 - avg_complexity, 1),
            'Security': round(avg_security, 1),
            'Scalability': round(3.5, 1),  # Default, could be enhanced
            'Reliability': round(4.0, 1)   # Default, could be enhanced
        }
    
    async def _generate_with_groq(self, context: Dict, reasoning_chain: List[str],
                                  knowledge: List[Dict], ai_model: AIModel) -> Dict:
        """Generate recommendation using Groq API"""
        if not self.groq_client:
            raise ValueError("Groq client not initialized. Check API key.")
        
        prompt = self._build_llm_prompt(context, reasoning_chain, knowledge)
        model_name = self.GROQ_MODELS[ai_model]
        
        # Call Groq API
        response = self.groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": VP.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        # Parse response
        response_text = response.choices[0].message.content
        return self._parse_llm_response(response_text)
    
    async def _generate_with_gemini(self, context: Dict, reasoning_chain: List[str],
                                   knowledge: List[Dict], ai_model: AIModel) -> Dict:
        """Generate recommendation using Google Gemini API"""
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized. Check API key.")
        
        prompt = self._build_llm_prompt(context, reasoning_chain, knowledge)
        model_name = self.GEMINI_MODELS[ai_model]
        
        # Initialize model
        model = genai.GenerativeModel(model_name)
        
        # Generate response
        response = model.generate_content(
            f"{VP.SYSTEM_PROMPT}\n\nContext: Cloud Recommendation\n{prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=2000,
            )
        )
        
        # Parse response
        response_text = response.text
        return self._parse_llm_response(response_text)
    
    def _build_llm_prompt(self, context: Dict, reasoning_chain: List[str],
                         knowledge: List[Dict]) -> str:
        """Build structured prompt for LLM with Cost-Narrative enhancement (Upgrade B)"""
        
        # Format knowledge context
        knowledge_context = "\n".join([
            f"- [{doc.get('provider', 'N/A')}] {doc.get('service', 'Unknown')}: {doc.get('content', '')[:200]}"
            for doc in knowledge[:5]
        ])
        
        # Format reasoning chain
        reasoning_text = "\n".join(reasoning_chain) if reasoning_chain else "Direct recommendation requested"
        
        # Check if this is a Terraform plan analysis
        is_plan_analysis = context.get('use_case') == 'terraform_plan_analysis'
        
        if is_plan_analysis:
            # Enhanced prompt for Terraform plan analysis (The Cloud DM)
            return f"""{VP.SYSTEM_PROMPT}

TERRAFORM PLAN TO ANALYZE:
{context.get('terraform_plan_output', 'No plan provided')}

CONTEXT:
{json.dumps(context, indent=2)}

Your mission: Don't just list changes. Analyze the **Financial Story** and **Risk Narrative** with surgical precision.

Provide your analysis in this JSON format:
{
  "summary": "One-sentence overview of architectural changes",
  "coffee_cup_cost": "Relatable cost comparison (e.g., 'equivalent to 2 lattes per day')",
  "blast_radius": {
    "security_risk": "What happens if this resource is compromised?",
    "impact_level": "low/medium/high/critical",
    "affected_systems": ["list of dependent systems"]
  },
  "treasure_hunt": {
    "optimization": "One specific optimization logic",
    "estimated_savings": "$50/month"
  },
  "environmental_impact": "Calculated impact (e.g., 'Powers a small website 24/7')",
  "warnings": ["List any architectural anomalies or risks"],
  "recommended_action": "approve/modify/reject"
}

Maintain absolute clarity."""
        
        else:
            # Standard recommendation prompt with cost narrative
            return f"""{VP.SYSTEM_PROMPT}

CONTEXT:
{json.dumps(context, indent=2)}

CHAIN-OF-THOUGHT REASONING:
{reasoning_text}

KNOWLEDGE BASE (Relevant Best Practices):
{knowledge_context}

Provide your recommendation in this JSON format with **human-friendly cost explanations**:
{{
  "recommended_service": "specific service name (e.g., EC2, Cloud Run, Azure VMs)",
  "provider": "aws/gcp/azure",
  "configuration": {{
    "instance_type": "e.g., t3.medium, e2-standard-2",
    "storage": "e.g., 100GB SSD",
    "key_settings": "important configuration details"
  }},
  "reasoning": "brief 2-3 sentence explanation of why this is the best choice",
  "estimated_monthly_cost": "$50-$100",
  "coffee_cup_cost": "e.g., 'Costs about 2 lattes per day' or '1 fancy coffee per week'",
  "real_world_analogy": "What this infrastructure is equivalent to (e.g., 'Serves a small blog with 1000 daily visitors')",
  "complexity": "low/medium/high",
  "setup_time": "e.g., 30 minutes",
  "blast_radius": "What breaks if this fails? (e.g., 'Website goes down for all users')",
  "alternatives": [
    {{
      "service": "alternative service name",
      "reason": "why this is an alternative",
      "trade_off": "what you gain/lose",
      "cost_difference": "cheaper/more expensive by X%"
    }}
  ]
}}

Remember: Bridge the gap between cloud jargon and human understanding!

Recommendation (JSON only):"""
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured recommendation"""
        try:
            # Try to parse JSON directly
            if response_text.strip().startswith('{'):
                return json.loads(response_text)
            
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.+?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try to find JSON object
            json_match = re.search(r'(\{.+\})', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Fallback to basic parsing
            return {'error': 'Could not parse response', 'raw_response': response_text}
        
        except json.JSONDecodeError as e:
            return {'error': f'JSON parse error: {e}', 'raw_response': response_text[:500]}
    
    def _generate_rule_based(self, context: Dict, reasoning_chain: List[str],
                           knowledge: List[Dict]) -> Dict:
        """Generate recommendation using rule-based approach (fallback)"""
        
        provider = context.get('provider', 'gcp')
        resource_type = context.get('resource_type', 'vm')
        budget = context.get('budget', 'medium')
        
        # Rule-based mapping
        recommendations = {
            'vm': {
                'aws': {'service': 'EC2', 'instance': 't3.medium', 'cost': '$30-$50'},
                'gcp': {'service': 'Compute Engine', 'instance': 'e2-standard-2', 'cost': '$50-$70'},
                'azure': {'service': 'Virtual Machines', 'instance': 'B2s', 'cost': '$40-$60'}
            },
            'database': {
                'aws': {'service': 'RDS MySQL', 'instance': 'db.t3.small', 'cost': '$25-$40'},
                'gcp': {'service': 'Cloud SQL', 'instance': 'db-n1-standard-1', 'cost': '$50-$80'},
                'azure': {'service': 'Azure SQL Database', 'instance': 'Basic', 'cost': '$5-$30'}
            }
        }
        
        rec = recommendations.get(resource_type, {}).get(provider, {
            'service': 'Managed Service',
            'instance': 'Standard',
            'cost': '$50-$100'
        })
        
        return {
            'recommended_service': rec['service'],
            'provider': provider,
            'configuration': {
                'instance_type': rec['instance'],
                'storage': '100GB SSD',
                'auto_scaling': budget != 'low'
            },
            'reasoning': f"Based on {budget} budget and {resource_type} requirements, {rec['service']} provides good balance of cost and performance.",
            'estimated_monthly_cost': rec['cost'],
            'complexity': 'medium',
            'alternatives': []
        }
    
    def _calculate_confidence(self, context: Dict, recommendation: Dict, knowledge: List[Dict]) -> float:
        """Calculate confidence score for recommendation"""
        confidence = 50.0  # Base confidence
        
        # Increase confidence if we have relevant knowledge
        if len(knowledge) > 5:
            confidence += 20.0
        
        # Increase if constraints are well-defined
        if context.get('budget') and context.get('resource_type'):
            confidence += 15.0
        
        # Increase if recommendation has detailed configuration
        if recommendation.get('configuration') and len(recommendation.get('configuration', {})) > 2:
            confidence += 15.0
        
        return min(100.0, confidence)
    
    def _compare_providers(self, context: Dict, knowledge: List[Dict]) -> Dict:
        """Compare providers when 'any' is selected"""
        providers = ['aws', 'gcp', 'azure']
        
        comparison = {}
        for provider in providers:
            provider_knowledge = [doc for doc in knowledge if doc.get('provider') == provider]
            
            if provider_knowledge:
                avg_cost = sum(doc.get('cost_score', 3) for doc in provider_knowledge) / len(provider_knowledge)
                avg_complexity = sum(doc.get('complexity_score', 3) for doc in provider_knowledge) / len(provider_knowledge)
                
                comparison[provider] = {
                    'cost_score': round(6.0 - avg_cost, 1),  # Invert so lower cost = higher score
                    'complexity_score': round(6.0 - avg_complexity, 1),
                    'knowledge_entries': len(provider_knowledge)
                }
        
        return comparison
