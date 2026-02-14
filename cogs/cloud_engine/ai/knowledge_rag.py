"""
Cloud Knowledge RAG System
Retrieval-Augmented Generation for cloud infrastructure recommendations
"""

import sqlite3
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class CloudKnowledgeRAG:
    """RAG system for cloud infrastructure recommendations using SQLite"""
    
    def __init__(self, db_path: str = "cloud_knowledge.db"):
        self.db_path = db_path
        # Simple keyword-based retrieval (no heavy dependencies like ChromaDB/sentence-transformers)
        # For production, consider adding sentence-transformers for semantic search
    
    def hybrid_search(self, query: str, provider: Optional[str] = None, 
                     category: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Hybrid search combining keyword matching and metadata filtering
        
        Args:
            query: Search query
            provider: Filter by provider (aws/gcp/azure)
            category: Filter by category (security/cost/performance/reliability)
            limit: Maximum results to return
            
        Returns:
            List of matching knowledge entries with scores
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if provider:
            where_clauses.append("provider = ?")
            params.append(provider)
        
        if category:
            where_clauses.append("category = ?")
            params.append(category)
        
        # Keyword search in content and service
        query_keywords = query.lower().split()
        if query_keywords:
            keyword_conditions = []
            for keyword in query_keywords:
                keyword_conditions.append("(LOWER(content) LIKE ? OR LOWER(service) LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            if keyword_conditions:
                where_clauses.append(f"({' OR '.join(keyword_conditions)})")
        
        where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Execute search with scoring
        cursor.execute(f"""
            SELECT 
                id, provider, service, category, content, source,
                impact_score, complexity_score, cost_score, security_score,
                created_at
            FROM cloud_knowledge 
            WHERE {where_str}
            ORDER BY impact_score DESC, security_score DESC
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            # Calculate relevance score based on keyword matches
            result['relevance_score'] = self._calculate_relevance(query, result['content'])
            results.append(result)
        
        conn.close()
        
        # Re-sort by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results[:limit]
    
    def search_patterns(self, use_case: str, provider: Optional[str] = None) -> List[Dict]:
        """Search for architecture patterns matching a use case"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Search patterns
        cursor.execute("""
            SELECT * FROM cloud_patterns
            WHERE LOWER(problem_statement) LIKE ? 
               OR LOWER(best_for) LIKE ?
               OR LOWER(pattern_name) LIKE ?
            ORDER BY pattern_name
            LIMIT 10
        """, (f"%{use_case.lower()}%", f"%{use_case.lower()}%", f"%{use_case.lower()}%"))
        
        patterns = []
        for row in cursor.fetchall():
            pattern = dict(row)
            # Parse JSON fields
            pattern['providers'] = json.loads(pattern['providers']) if pattern['providers'] else []
            pattern['services'] = json.loads(pattern['services']) if pattern['services'] else []
            
            # Filter by provider if specified
            if provider and provider not in pattern['providers']:
                continue
            
            patterns.append(pattern)
        
        conn.close()
        return patterns
    
    def get_related_knowledge(self, service: str, provider: str) -> List[Dict]:
        """Get all knowledge related to a specific service and provider"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cloud_knowledge
            WHERE provider = ? AND service = ?
            ORDER BY impact_score DESC
        """, (provider, service))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_by_category(self, category: str, provider: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get knowledge entries by category"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if provider:
            cursor.execute("""
                SELECT * FROM cloud_knowledge
                WHERE category = ? AND provider = ?
                ORDER BY impact_score DESC
                LIMIT ?
            """, (category, provider, limit))
        else:
            cursor.execute("""
                SELECT * FROM cloud_knowledge
                WHERE category = ?
                ORDER BY impact_score DESC
                LIMIT ?
            """, (category, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """Calculate relevance score based on keyword matches"""
        query_keywords = set(query.lower().split())
        content_lower = content.lower()
        
        # Count keyword matches
        matches = sum(1 for keyword in query_keywords if keyword in content_lower)
        
        # Normalize by query length
        if len(query_keywords) == 0:
            return 0.0
        
        return (matches / len(query_keywords)) * 100.0
    
    def _merge_results(self, vector_results: List, keyword_results: List[Dict], limit: int) -> List[Dict]:
        """Merge and deduplicate results from different search methods"""
        # For future implementation with vector search
        # Currently just uses keyword results
        seen_ids = set()
        merged = []
        
        for result in keyword_results:
            if result['id'] not in seen_ids:
                seen_ids.add(result['id'])
                merged.append(result)
        
        return merged[:limit]
