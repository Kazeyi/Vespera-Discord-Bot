"""
Memory Optimizer for Discord Bot
Tackles high memory usage (800MB → target <400MB)
"""

import gc
import sys
import weakref
from functools import lru_cache
from typing import Any, Dict, List, Optional


class MemoryOptimizer:
    """Aggressive memory optimization for Discord bot"""
    
    # Cache limits (reduced from potential unlimited)
    MAX_CACHE_SIZE = 128  # LRU cache max entries
    SMALL_CACHE_SIZE = 32  # For frequently accessed small data
    
    @staticmethod
    def optimize_gc():
        """Optimize garbage collection for lower memory"""
        # More aggressive GC
        gc.set_threshold(400, 5, 5)  # Reduced from defaults (700, 10, 10)
        
        # Collect immediately
        gc.collect(2)  # Full collection
        
    @staticmethod
    def clear_all_caches():
        """Clear all LRU caches in the system"""
        gc.collect()
        
        # Clear cache wrappers
        for obj in gc.get_objects():
            if hasattr(obj, 'cache_clear') and callable(obj.cache_clear):
                try:
                    obj.cache_clear()
                except:
                    pass
    
    @staticmethod
    def get_memory_mb() -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    @staticmethod
    def memory_report() -> Dict[str, Any]:
        """Generate memory usage report"""
        mem_mb = MemoryOptimizer.get_memory_mb()
        
        # Count cached objects (safely)
        cache_count = 0
        for obj in gc.get_objects():
            try:
                if hasattr(obj, '__name__'):
                    obj_name = getattr(obj, '__name__', '')
                    if isinstance(obj_name, str) and 'cache' in obj_name.lower():
                        cache_count += 1
            except (AttributeError, TypeError, RuntimeError):
                continue
        
        return {
            'memory_mb': mem_mb,
            'memory_status': 'OK' if mem_mb < 400 else 'HIGH' if mem_mb < 700 else 'CRITICAL',
            'gc_stats': gc.get_stats(),
            'gc_count': gc.get_count(),
            'cached_objects': cache_count
        }
    
    @staticmethod
    def lightweight_cache(maxsize=SMALL_CACHE_SIZE):
        """Lightweight LRU cache decorator"""
        return lru_cache(maxsize=maxsize)
    
    @staticmethod
    def cleanup_on_low_memory():
        """Emergency cleanup when memory is high"""
        mem = MemoryOptimizer.get_memory_mb()
        
        if mem > 700:  # Critical threshold
            print(f"🚨 [Memory] CRITICAL: {mem:.1f}MB - Emergency cleanup")
            MemoryOptimizer.clear_all_caches()
            gc.collect(2)
            
            new_mem = MemoryOptimizer.get_memory_mb()
            print(f"✅ [Memory] Freed {mem - new_mem:.1f}MB → {new_mem:.1f}MB")
            
        elif mem > 500:  # Warning threshold
            print(f"⚠️ [Memory] HIGH: {mem:.1f}MB - Collecting garbage")
            gc.collect(1)


# Singleton instance
memory_optimizer = MemoryOptimizer()


# Optimized data structures
class LimitedDict(dict):
    """Dictionary with size limit (FIFO eviction)"""
    
    def __init__(self, max_size: int = 1000):
        super().__init__()
        self.max_size = max_size
        self._keys_order = []
    
    def __setitem__(self, key, value):
        if key not in self and len(self) >= self.max_size:
            # Remove oldest key
            oldest = self._keys_order.pop(0)
            del self[oldest]
        
        super().__setitem__(key, value)
        
        if key not in self._keys_order:
            self._keys_order.append(key)


class LazyLoader:
    """Lazy load heavy objects only when needed"""
    
    def __init__(self, loader_func):
        self.loader_func = loader_func
        self._cache = None
    
    def get(self):
        if self._cache is None:
            self._cache = self.loader_func()
        return self._cache
    
    def clear(self):
        self._cache = None
        gc.collect()


# Memory-efficient string handling
class StringPool:
    """String interning pool to reduce duplicate strings"""
    
    _pool: Dict[str, str] = {}
    
    @classmethod
    def intern(cls, s: str) -> str:
        """Intern string to save memory"""
        if s not in cls._pool:
            cls._pool[s] = sys.intern(s)
        return cls._pool[s]
    
    @classmethod
    def clear(cls):
        """Clear pool"""
        cls._pool.clear()


# Auto-cleanup decorator
def auto_cleanup(func):
    """Decorator to auto-cleanup after function execution"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Periodic cleanup
            if hasattr(wrapper, '_call_count'):
                wrapper._call_count += 1
            else:
                wrapper._call_count = 1
            
            # Cleanup every 100 calls
            if wrapper._call_count % 100 == 0:
                gc.collect(0)
    
    return wrapper
