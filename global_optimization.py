"""
Global RAM Optimization System
Shared utilities for all cogs to minimize memory usage on 1GB RAM / 1-core CPU

Features:
✅ Centralized garbage collection
✅ String interning pool
✅ SQLite WAL mode enabler
✅ Memory monitoring
✅ Cache size limits
"""

import gc
import sys
import sqlite3
import time
from typing import Dict, Any, Optional
import os

# Global string interning pool (shared across all cogs)
_GLOBAL_INTERN_POOL: Dict[str, str] = {}
_POOL_SIZE_LIMIT = 10000  # Max 10k interned strings


def intern_string(s: str) -> str:
    """
    Intern a string to save memory
    All identical strings point to same memory address
    
    Args:
        s: String to intern
        
    Returns:
        Interned string
    """
    if s not in _GLOBAL_INTERN_POOL:
        if len(_GLOBAL_INTERN_POOL) >= _POOL_SIZE_LIMIT:
            # Clear pool if it gets too large
            _GLOBAL_INTERN_POOL.clear()
            print(f"🧹 String intern pool cleared (reached {_POOL_SIZE_LIMIT} limit)")
        
        _GLOBAL_INTERN_POOL[s] = sys.intern(str(s))
    
    return _GLOBAL_INTERN_POOL[s]


def clear_intern_pool():
    """Clear the global string interning pool"""
    count = len(_GLOBAL_INTERN_POOL)
    _GLOBAL_INTERN_POOL.clear()
    print(f"🧹 Cleared {count} interned strings")


def force_garbage_collection() -> int:
    """
    Force Python garbage collection
    
    Returns:
        Number of objects freed
    """
    return gc.collect()


def enable_wal_mode(db_path: str):
    """
    Enable SQLite WAL (Write-Ahead Logging) mode for a database
    Allows concurrent reads and writes
    
    Args:
        db_path: Path to SQLite database file
    """
    if not os.path.exists(db_path):
        print(f"⚠️ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # Set synchronous to NORMAL for faster writes (still safe)
    cursor.execute("PRAGMA synchronous=NORMAL;")
    
    # Optimize cache size (32MB)
    cursor.execute("PRAGMA cache_size=-32000;")
    
    # Set temp store to memory for speed
    cursor.execute("PRAGMA temp_store=MEMORY;")
    
    # Enable memory-mapped I/O for reads (16MB)
    cursor.execute("PRAGMA mmap_size=16777216;")
    
    conn.commit()
    conn.close()
    
    print(f"✅ SQLite WAL mode enabled: {db_path}")


def get_memory_info() -> Dict[str, Any]:
    """
    Get current memory statistics
    
    Returns:
        Dict with memory info
    """
    import resource
    
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            'max_rss_mb': usage.ru_maxrss / 1024,  # Convert KB to MB
            'user_time': usage.ru_utime,
            'system_time': usage.ru_stime,
            'intern_pool_size': len(_GLOBAL_INTERN_POOL)
        }
    except Exception as e:
        return {'error': str(e)}


class MemoryOptimizer:
    """
    Central memory optimization manager
    Run as a background task in the bot
    """
    
    def __init__(self):
        self.last_gc_time = time.time()
        self.gc_interval = 1800  # 30 minutes
        self.gc_history = []
        
    def should_run_gc(self) -> bool:
        """Check if GC should run"""
        return (time.time() - self.last_gc_time) >= self.gc_interval
    
    def run_gc(self) -> Dict[str, Any]:
        """
        Run garbage collection and return stats
        
        Returns:
            Dict with GC stats
        """
        start_time = time.time()
        
        # Force full GC across all generations
        collected_0 = gc.collect(0)  # Young objects
        collected_1 = gc.collect(1)  # Middle-aged objects
        collected_2 = gc.collect(2)  # Old objects
        
        total_collected = collected_0 + collected_1 + collected_2
        duration = time.time() - start_time
        
        self.last_gc_time = time.time()
        
        stats = {
            'total_collected': total_collected,
            'gen0': collected_0,
            'gen1': collected_1,
            'gen2': collected_2,
            'duration_ms': duration * 1000,
            'timestamp': time.time()
        }
        
        self.gc_history.append(stats)
        
        # Keep only last 100 GC runs
        if len(self.gc_history) > 100:
            self.gc_history = self.gc_history[-100:]
        
        print(f"🗑️ GC: {total_collected} objects freed in {duration*1000:.1f}ms")
        
        return stats
    
    def get_gc_stats(self) -> Dict[str, Any]:
        """Get GC statistics"""
        if not self.gc_history:
            return {'message': 'No GC runs yet'}
        
        total_collected = sum(s['total_collected'] for s in self.gc_history)
        avg_duration = sum(s['duration_ms'] for s in self.gc_history) / len(self.gc_history)
        
        return {
            'total_runs': len(self.gc_history),
            'total_objects_freed': total_collected,
            'avg_duration_ms': avg_duration,
            'last_run': self.gc_history[-1] if self.gc_history else None
        }


# Global optimizer instance
_global_optimizer = MemoryOptimizer()


def get_memory_optimizer() -> MemoryOptimizer:
    """Get the global memory optimizer instance"""
    return _global_optimizer


def optimize_all_databases(*db_paths: str):
    """
    Optimize multiple databases with WAL mode
    
    Args:
        *db_paths: Variable number of database paths
    """
    for db_path in db_paths:
        if db_path:
            enable_wal_mode(db_path)


def vacuum_database(db_path: str):
    """
    Run VACUUM on database to reclaim space
    WARNING: This locks the database briefly
    
    Args:
        db_path: Path to SQLite database
    """
    if not os.path.exists(db_path):
        print(f"⚠️ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"🗜️ Vacuuming database: {db_path}")
    cursor.execute("VACUUM;")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database vacuumed: {db_path}")


def analyze_database(db_path: str):
    """
    Run ANALYZE on database to update query planner statistics
    
    Args:
        db_path: Path to SQLite database
    """
    if not os.path.exists(db_path):
        print(f"⚠️ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("ANALYZE;")
    
    conn.commit()
    conn.close()
    
    print(f"📊 Database analyzed: {db_path}")


# Auto-initialize on import
def initialize_global_optimizations():
    """Initialize all global optimizations"""
    print("🚀 Initializing global RAM optimizations...")
    
    # Set garbage collection thresholds (more aggressive)
    gc.set_threshold(700, 10, 10)  # Default is (700, 10, 10)
    
    # Enable automatic GC
    gc.enable()
    
    print("✅ Global RAM optimizations initialized")


# Run on module import
initialize_global_optimizations()
