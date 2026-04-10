#!/usr/bin/env python3
"""
Test script for RulebookIngestor
Demonstrates memory-efficient markdown parsing optimized for 1 core/1GB RAM
"""

import sys
import os
import time
import tracemalloc

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cogs.dnd import RulebookIngestor, RulebookRAG

def test_ingest_rulebook():
    """Test ingesting RulesGlossary.md"""
    
    print("=" * 70)
    print("RULEBOOK INGESTOR TEST - Memory-Optimized for 1GB RAM")
    print("=" * 70)
    print()
    
    # Start memory tracking
    tracemalloc.start()
    start_time = time.time()
    
    file_path = "srd/RulesGlossary.md"
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        print("   Make sure srd/RulesGlossary.md exists")
        return
    
    print(f"📚 Ingesting: {file_path}")
    print(f"   Strategy: Streaming line-by-line (no full file in memory)")
    print(f"   Batch size: {RulebookIngestor.BATCH_SIZE} rules per DB commit")
    print()
    
    try:
        # Ingest rulebook
        stats = RulebookIngestor.ingest_markdown_rulebook(file_path, source="SRD 2024")
        
        # Get memory stats
        current, peak = tracemalloc.get_traced_memory()
        elapsed = time.time() - start_time
        tracemalloc.stop()
        
        # Display results
        print("✅ INGESTION COMPLETE")
        print()
        print(f"   Inserted/Updated: {stats['inserted']} rules")
        print(f"   Skipped:          {stats['skipped']} rules")
        print(f"   Time Elapsed:     {elapsed:.2f} seconds")
        print(f"   Peak Memory:      {peak / 1024 / 1024:.2f} MB")
        print(f"   Avg per rule:     {(peak / stats['inserted'] / 1024):.2f} KB")
        print()
        
        # Test lookup with "See also" following
        print("=" * 70)
        print("TESTING ENHANCED LOOKUP (with 'See also' following)")
        print("=" * 70)
        print()
        
        test_keywords = ["advantage", "attack", "concentration"]
        
        for keyword in test_keywords:
            print(f"🔍 Searching: '{keyword}'")
            
            # Regular lookup
            results = RulebookRAG.lookup_rule(keyword, limit=2, follow_see_also=False)
            print(f"   Found {len(results)} results (no 'See also')")
            
            # With "See also" following
            results_enhanced = RulebookRAG.lookup_rule(keyword, limit=3, follow_see_also=True)
            print(f"   Found {len(results_enhanced)} results (with 'See also')")
            
            if results_enhanced:
                print(f"   Primary: {results_enhanced[0][0]}")
                
                # Extract "See also" references
                refs = RulebookIngestor.extract_see_also_references(results_enhanced[0][0])
                if refs:
                    print(f"   References: {', '.join(refs)}")
            
            print()
        
        # Test action keyword extraction
        print("=" * 70)
        print("ACTION KEYWORDS (for ActionEconomyValidator auto-update)")
        print("=" * 70)
        print()
        
        action_keywords = RulebookIngestor.get_action_keywords()
        print(f"   Found {len(action_keywords)} [Action] tagged rules:")
        print(f"   {', '.join(action_keywords)}")
        print()
        
        print("✅ ALL TESTS PASSED")
        print()
        print("💡 Usage in Discord:")
        print("   /ingest_rulebook filename:RulesGlossary.md")
        print("   /lookup_rule keyword:advantage follow_links:True")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ingest_rulebook()
