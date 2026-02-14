"""
Cloud Knowledge Ingestor
Ingests cloud best practices, documentation, and security guidelines into vector database
"""

import sqlite3
import os
import re
import json
from typing import Dict, List, Optional
from datetime import datetime


class CloudKnowledgeIngestor:
    """Ingest cloud best practices, documentation, and security guidelines"""
    
    PROVIDER_PATTERNS = {
        'aws': re.compile(r'# AWS (.+?)(?:\s+\[(.+?)\])?\s*$'),
        'gcp': re.compile(r'# GCP (.+?)(?:\s+\[(.+?)\])?\s*$'),
        'azure': re.compile(r'# Azure (.+?)(?:\s+\[(.+?)\])?\s*$')
    }
    
    CATEGORY_MAPPING = {
        'security': ['security', 'iam', 'encryption', 'compliance', 'firewall', 'vpc'],
        'cost': ['cost', 'pricing', 'budget', 'optimization', 'savings', 'billing'],
        'performance': ['performance', 'scaling', 'latency', 'throughput', 'cpu', 'memory'],
        'reliability': ['reliability', 'availability', 'redundancy', 'backup', 'disaster']
    }
    
    def __init__(self, db_path: str = "cloud_knowledge.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database for cloud knowledge"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main knowledge base
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cloud_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                service TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                impact_score REAL DEFAULT 50.0,
                complexity_score REAL DEFAULT 3.0,
                cost_score REAL DEFAULT 3.0,
                security_score REAL DEFAULT 3.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Use cases and patterns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cloud_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL,
                problem_statement TEXT,
                solution TEXT,
                providers TEXT,
                services TEXT,
                architecture_diagram TEXT,
                best_for TEXT,
                alternatives TEXT,
                complexity TEXT,
                estimated_cost_range TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_provider 
            ON cloud_knowledge(provider)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_category 
            ON cloud_knowledge(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_service 
            ON cloud_knowledge(service)
        """)
        
        conn.commit()
        conn.close()
    
    def ingest_cloud_documentation(self, file_path: str, provider: str, source: str = "official_docs"):
        """Ingest markdown documentation with structured metadata"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Documentation file not found: {file_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse markdown with headers
        sections = re.split(r'\n##\s+', content)
        ingested_count = 0
        
        for section in sections:
            if not section.strip():
                continue
            
            # Extract section header and content
            lines = section.strip().split('\n')
            if not lines:
                continue
            
            header = lines[0]
            body = '\n'.join(lines[1:])
            
            # Extract service and category from header
            service = header.split('(')[0].strip() if '(' in header else header.strip()
            
            # Extract category from brackets [category] or infer from content
            category_match = re.search(r'\[(.+?)\]', header)
            category = category_match.group(1) if category_match else self._categorize_content(body)
            
            # Calculate scores based on content analysis
            scores = self._calculate_scores(body, category)
            
            cursor.execute("""
                INSERT INTO cloud_knowledge 
                (provider, service, category, content, source, impact_score, 
                 complexity_score, cost_score, security_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                provider, service, category, body, source,
                scores['impact'], scores['complexity'],
                scores['cost'], scores['security']
            ))
            ingested_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Ingested {ingested_count} sections from {file_path}")
        return ingested_count
    
    def ingest_pattern(self, pattern: Dict):
        """Ingest a cloud architecture pattern"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cloud_patterns 
            (pattern_name, problem_statement, solution, providers, services,
             architecture_diagram, best_for, alternatives, complexity, estimated_cost_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern['pattern_name'],
            pattern.get('problem_statement'),
            pattern.get('solution'),
            json.dumps(pattern.get('providers', [])),
            json.dumps(pattern.get('services', [])),
            pattern.get('architecture_diagram'),
            pattern.get('best_for'),
            pattern.get('alternatives'),
            pattern.get('complexity', 'medium'),
            pattern.get('estimated_cost_range')
        ))
        
        conn.commit()
        conn.close()
    
    def _categorize_content(self, content: str) -> str:
        """Automatically categorize content based on keywords"""
        content_lower = content.lower()
        
        category_scores = {}
        for category, keywords in self.CATEGORY_MAPPING.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return "general"
    
    def _calculate_scores(self, content: str, category: str) -> Dict[str, float]:
        """Calculate various scores for content analysis"""
        content_lower = content.lower()
        
        # Impact score - based on importance keywords
        importance_keywords = ['must', 'critical', 'essential', 'required', 'important', 'recommended']
        keywords_present = sum(1 for w in importance_keywords if w in content_lower)
        impact_score = min(100.0, 30.0 + keywords_present * 15)
        
        # Complexity score - based on content length and technical terms
        technical_terms = ['configure', 'implement', 'deploy', 'integrate', 'customize']
        tech_count = sum(1 for term in technical_terms if term in content_lower)
        complexity = min(5.0, 2.0 + (tech_count * 0.4) + (len(content) / 500))
        
        return {
            'impact': impact_score,
            'complexity': complexity,
            'cost': self._estimate_cost_impact(content_lower),
            'security': self._estimate_security_impact(content_lower, category)
        }
    
    def _estimate_cost_impact(self, content: str) -> float:
        """Estimate cost impact (1=low, 5=high)"""
        cost_keywords = ['expensive', 'costly', 'premium', 'high cost', 'enterprise']
        savings_keywords = ['cheap', 'low cost', 'savings', 'optimize', 'reduce cost', 'free tier']
        
        cost_count = sum(1 for kw in cost_keywords if kw in content)
        savings_count = sum(1 for kw in savings_keywords if kw in content)
        
        if cost_count > savings_count:
            return min(5.0, 3.0 + cost_count * 0.5)
        elif savings_count > cost_count:
            return max(1.0, 3.0 - savings_count * 0.5)
        
        return 3.0
    
    def _estimate_security_impact(self, content: str, category: str) -> float:
        """Estimate security impact (1=low, 5=high)"""
        if category == 'security':
            return 4.5
        
        security_keywords = ['encrypt', 'secure', 'private', 'vpc', 'firewall', 
                           'iam', 'authentication', 'authorization', 'compliance']
        
        score = 2.0  # Base score
        score += sum(0.3 for kw in security_keywords if kw in content)
        
        return min(5.0, score)
    
    def get_knowledge_stats(self) -> Dict:
        """Get statistics about the knowledge base"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total entries
        cursor.execute("SELECT COUNT(*) FROM cloud_knowledge")
        total_entries = cursor.fetchone()[0]
        
        # By provider
        cursor.execute("""
            SELECT provider, COUNT(*) 
            FROM cloud_knowledge 
            GROUP BY provider
        """)
        by_provider = dict(cursor.fetchall())
        
        # By category
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM cloud_knowledge 
            GROUP BY category
        """)
        by_category = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_entries': total_entries,
            'by_provider': by_provider,
            'by_category': by_category
        }
