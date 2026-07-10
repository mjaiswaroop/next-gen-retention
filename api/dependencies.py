import time
import redis
from fastapi import HTTPException, Depends, Request
from auth import get_current_user
from config import settings

# Initialize Redis pool
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

class RateLimiter:
    """
    Redis-backed Fixed-Window Rate Limiter.
    Limits requests per minute per tenant.
    """
    def __init__(self, requests_per_minute: int = 20):
        self.requests_per_minute = requests_per_minute

    def __call__(self, request: Request, current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Use the current minute as the window bucket
        current_minute = int(time.time() / 60)
        route_path = request.url.path
        
        # Redis Key: rate_limit:{tenant_id}:{route_path}:{current_minute}
        redis_key = f"rate_limit:{tenant_id}:{route_path}:{current_minute}"
        
        # Increment the counter for this window
        try:
            current_count = redis_client.incr(redis_key)
            if current_count == 1:
                # Set expiry slightly longer than the window to clean up
                redis_client.expire(redis_key, 120)
                
            if current_count > self.requests_per_minute:
                raise HTTPException(
                    status_code=429, 
                    detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute allowed."
                )
        except redis.RedisError as e:
            # Fall open in case of Redis failure (availability over strict limit)
            import logging
            logging.getLogger("retention_core.rate_limiter").warning(f"Redis rate limiting failed: {e}")
        
        return current_user
