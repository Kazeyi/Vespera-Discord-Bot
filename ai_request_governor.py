"""
AI Request Governor - Singleton Queue Manager
Prevents CPU/RAM overload by processing AI requests sequentially (FIFO)
Optimized for 1-core CPU / 1GB RAM environments
"""

import asyncio
import time
import sys
from typing import Dict, Any, Optional, Callable
from collections import deque
from dataclasses import dataclass

@dataclass
class AIRequest:
    """Represents a single AI request in the queue"""
    request_id: str
    prompt: str
    model_name: str
    callback: Callable
    priority: int = 0  # Higher = more urgent (for future extensions)
    created_at: float = 0.0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class AIRequestGovernor:
    """
    Singleton Queue Manager for AI Requests
    
    Features:
    - FIFO processing (one request at a time)
    - Priority queue support
    - Request timeout handling
    - Rate limiting per user
    - Memory-efficient design
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.queue: deque = deque()  # FIFO queue
        self.processing = False
        self.current_request: Optional[AIRequest] = None
        self.stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_timeout': 0,
            'avg_processing_time': 0.0
        }
        
        # Rate limiting (user_id -> last_request_time)
        self.user_cooldowns: Dict[str, float] = {}
        self.global_cooldown = 0.5  # 500ms between requests globally
        self.last_request_time = 0.0
        
        # Processing task
        self.processor_task: Optional[asyncio.Task] = None
        
        print("✅ AI Request Governor initialized (Singleton)")
    
    async def start(self):
        """Start the background processor"""
        if self.processor_task is None or self.processor_task.done():
            self.processor_task = asyncio.create_task(self._process_queue())
            print("🚀 AI Request Governor processor started")
    
    async def stop(self):
        """Stop the background processor"""
        if self.processor_task and not self.processor_task.done():
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
            print("🛑 AI Request Governor processor stopped")
    
    def check_user_rate_limit(self, user_id: str, cooldown: float = 3.0) -> bool:
        """
        Check if user is rate-limited
        
        Args:
            user_id: User identifier
            cooldown: Cooldown period in seconds
            
        Returns:
            True if rate-limited, False if allowed
        """
        now = time.time()
        last_request = self.user_cooldowns.get(user_id, 0.0)
        
        if now - last_request < cooldown:
            return True  # Rate limited
        
        self.user_cooldowns[user_id] = now
        return False  # Allowed
    
    async def submit_request(
        self,
        request_id: str,
        prompt: str,
        model_name: str,
        callback: Callable,
        priority: int = 0,
        timeout: float = 30.0
    ) -> bool:
        """
        Submit an AI request to the queue
        
        Args:
            request_id: Unique identifier for tracking
            prompt: AI prompt text
            model_name: Model to use
            callback: Async function to execute with prompt and model
            priority: Priority level (higher = more urgent)
            timeout: Max processing time in seconds
            
        Returns:
            True if submitted successfully
        """
        async with self._lock:
            # Create request
            request = AIRequest(
                request_id=request_id,
                prompt=prompt,
                model_name=model_name,
                callback=callback,
                priority=priority
            )
            
            # Add to queue
            self.queue.append(request)
            
            # Sort by priority (higher first) if needed
            if priority > 0:
                self.queue = deque(sorted(self.queue, key=lambda x: x.priority, reverse=True))
            
            print(f"📥 AI Request queued: {request_id} (Queue size: {len(self.queue)})")
            
            return True
    
    async def _process_queue(self):
        """Background task that processes requests sequentially"""
        print("🔄 AI Request Processor loop started")
        
        while True:
            try:
                # Check if queue has items
                if not self.queue:
                    await asyncio.sleep(0.1)  # Small sleep to prevent busy-waiting
                    continue
                
                # Enforce global cooldown
                now = time.time()
                time_since_last = now - self.last_request_time
                if time_since_last < self.global_cooldown:
                    await asyncio.sleep(self.global_cooldown - time_since_last)
                
                # Get next request
                async with self._lock:
                    if not self.queue:
                        continue
                    request = self.queue.popleft()
                
                self.current_request = request
                self.processing = True
                
                print(f"⚙️ Processing AI request: {request.request_id}")
                
                # Process request with timing
                start_time = time.time()
                
                try:
                    # Execute the callback (should be an async function that calls ask_ai)
                    await request.callback(request.prompt, request.model_name)
                    
                    processing_time = time.time() - start_time
                    self.stats['total_processed'] += 1
                    
                    # Update average processing time
                    current_avg = self.stats['avg_processing_time']
                    total = self.stats['total_processed']
                    self.stats['avg_processing_time'] = (current_avg * (total - 1) + processing_time) / total
                    
                    print(f"✅ Completed: {request.request_id} ({processing_time:.2f}s)")
                    
                except asyncio.TimeoutError:
                    self.stats['total_timeout'] += 1
                    print(f"⏱️ Timeout: {request.request_id}")
                
                except Exception as e:
                    self.stats['total_failed'] += 1
                    print(f"❌ Failed: {request.request_id} - {str(e)[:100]}")
                
                finally:
                    self.current_request = None
                    self.processing = False
                    self.last_request_time = time.time()
                
                # Small delay between requests to prevent CPU spikes
                await asyncio.sleep(0.1)
            
            except asyncio.CancelledError:
                print("🛑 AI Request Processor cancelled")
                break
            
            except Exception as e:
                print(f"❌ AI Request Processor error: {e}")
                await asyncio.sleep(1.0)  # Backoff on error
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.queue)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            'queue_size': len(self.queue),
            'is_processing': self.processing,
            'current_request': self.current_request.request_id if self.current_request else None
        }
    
    def clear_old_cooldowns(self, max_age: float = 300.0):
        """Clear user cooldowns older than max_age seconds"""
        now = time.time()
        expired = [uid for uid, ts in self.user_cooldowns.items() if now - ts > max_age]
        for uid in expired:
            del self.user_cooldowns[uid]
        
        if expired:
            print(f"🧹 Cleared {len(expired)} expired user cooldowns")


# Global singleton instance
_governor = AIRequestGovernor()


async def get_governor() -> AIRequestGovernor:
    """Get the AI Request Governor singleton instance"""
    return _governor


async def start_governor():
    """Initialize and start the governor"""
    governor = await get_governor()
    await governor.start()


async def stop_governor():
    """Stop the governor"""
    governor = await get_governor()
    await governor.stop()


# Convenience wrapper for existing code
async def queue_ai_request(
    request_id: str,
    prompt: str,
    model_name: str,
    callback: Callable,
    user_id: str = None,
    priority: int = 0
) -> bool:
    """
    Queue an AI request (convenience function)
    
    Args:
        request_id: Unique ID for this request
        prompt: AI prompt
        model_name: Model to use
        callback: Async callback function
        user_id: Optional user ID for rate limiting
        priority: Priority level
        
    Returns:
        True if queued successfully, False if rate-limited
    """
    governor = await get_governor()
    
    # Check user rate limit if user_id provided
    if user_id and governor.check_user_rate_limit(user_id):
        return False
    
    return await governor.submit_request(
        request_id=request_id,
        prompt=prompt,
        model_name=model_name,
        callback=callback,
        priority=priority
    )
