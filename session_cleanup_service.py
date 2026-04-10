# --- Session Cleanup Service ---
"""
Ephemeral Session Manager
Prevents memory leaks by automatically cleaning up expired deployment sessions

Runs as a background task to expire old sessions
"""

import asyncio
import time
from datetime import datetime, timedelta
import cloud_database as cloud_db


class SessionCleanupService:
    """
    Service to clean up expired deployment sessions
    Prevents memory leaks from abandoned project IDs
    """
    
    def __init__(self, cleanup_interval_minutes: int = 5):
        self.cleanup_interval = cleanup_interval_minutes * 60
        self.is_running = False
        self._task = None
    
    async def start(self):
        """Start the cleanup service"""
        if self.is_running:
            print("⚠️  SessionCleanupService already running")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        print(f"✅ SessionCleanupService started (interval: {self.cleanup_interval / 60}min)")
    
    async def stop(self):
        """Stop the cleanup service"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("🛑 SessionCleanupService stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.is_running:
            try:
                # Run cleanup
                expired_count = cloud_db.cleanup_expired_sessions()
                
                if expired_count > 0:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"🧹 [{timestamp}] SessionCleanupService: Cleaned {expired_count} expired sessions")
                
                # Clear old policy cache
                self._cleanup_policy_cache()
                
                # Wait for next interval
                await asyncio.sleep(self.cleanup_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ SessionCleanupService error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def _cleanup_policy_cache(self):
        """Clean up expired policy cache entries"""
        try:
            import sqlite3
            conn = sqlite3.connect(cloud_db.CLOUD_DB_FILE)
            cursor = conn.cursor()
            
            current_time = time.time()
            
            cursor.execute("""
                DELETE FROM policy_cache 
                WHERE expires_at < ?
            """, (current_time,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                print(f"🧹 Cleaned {deleted_count} expired policy cache entries")
        
        except Exception as e:
            print(f"⚠️  Policy cache cleanup error: {e}")
    
    def force_cleanup(self) -> dict:
        """Force immediate cleanup (for testing/manual trigger)"""
        print("🔧 Force cleanup triggered...")
        
        # Clean expired sessions
        expired_sessions = cloud_db.cleanup_expired_sessions()
        
        # Clean policy cache
        self._cleanup_policy_cache()
        
        # Clean up old deployment history (older than 90 days)
        old_history = self._cleanup_old_history(days=90)
        
        result = {
            'expired_sessions': expired_sessions,
            'old_history_cleaned': old_history,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Force cleanup complete: {result}")
        return result
    
    def _cleanup_old_history(self, days: int = 90) -> int:
        """Clean up old deployment history"""
        try:
            import sqlite3
            conn = sqlite3.connect(cloud_db.CLOUD_DB_FILE)
            cursor = conn.cursor()
            
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            cursor.execute("""
                DELETE FROM deployment_history 
                WHERE created_at < ? AND status IN ('completed', 'failed', 'cancelled')
            """, (cutoff_time,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                print(f"🧹 Cleaned {deleted_count} old deployment history entries (>{days} days)")
            
            return deleted_count
        
        except Exception as e:
            print(f"⚠️  History cleanup error: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """Get cleanup service statistics"""
        import sqlite3
        conn = sqlite3.connect(cloud_db.CLOUD_DB_FILE)
        cursor = conn.cursor()
        
        # Count active sessions
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_sessions 
            WHERE status IN ('pending', 'approved', 'deploying')
        """)
        active_sessions = cursor.fetchone()[0]
        
        # Count expired sessions
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_sessions 
            WHERE status = 'expired'
        """)
        expired_sessions = cursor.fetchone()[0]
        
        # Count total sessions
        cursor.execute("SELECT COUNT(*) FROM deployment_sessions")
        total_sessions = cursor.fetchone()[0]
        
        # Count cache entries
        cursor.execute("SELECT COUNT(*) FROM policy_cache")
        cache_entries = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'active_sessions': active_sessions,
            'expired_sessions': expired_sessions,
            'total_sessions': total_sessions,
            'cache_entries': cache_entries,
            'is_running': self.is_running,
            'cleanup_interval_minutes': self.cleanup_interval / 60
        }


# Global instance
_cleanup_service = None


def get_cleanup_service() -> SessionCleanupService:
    """Get or create the global cleanup service instance"""
    global _cleanup_service
    
    if _cleanup_service is None:
        _cleanup_service = SessionCleanupService(cleanup_interval_minutes=5)
    
    return _cleanup_service


async def start_cleanup_service():
    """Start the global cleanup service"""
    service = get_cleanup_service()
    await service.start()


async def stop_cleanup_service():
    """Stop the global cleanup service"""
    service = get_cleanup_service()
    await service.stop()


def force_cleanup():
    """Force immediate cleanup"""
    service = get_cleanup_service()
    return service.force_cleanup()


def get_service_stats():
    """Get cleanup service statistics"""
    service = get_cleanup_service()
    return service.get_stats()


if __name__ == "__main__":
    # Test the cleanup service
    import asyncio
    
    async def test_cleanup():
        print("🧪 Testing SessionCleanupService...")
        
        # Initialize database
        cloud_db.init_cloud_database()
        
        # Start service
        service = get_cleanup_service()
        await service.start()
        
        # Wait a bit
        print("⏳ Running for 30 seconds...")
        await asyncio.sleep(30)
        
        # Get stats
        stats = service.get_stats()
        print(f"📊 Service Stats: {stats}")
        
        # Force cleanup
        result = service.force_cleanup()
        print(f"🔧 Force Cleanup Result: {result}")
        
        # Stop service
        await service.stop()
        
        print("✅ Test complete")
    
    asyncio.run(test_cleanup())
