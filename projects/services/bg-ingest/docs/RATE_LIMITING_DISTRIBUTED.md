# Extending Rate Limiting with Distributed Storage

## Overview

The current rate limiter implementation uses an in-memory dictionary to store rate limit buckets. While this works well for single-instance deployments, it has limitations in distributed environments:

- **No sharing between instances**: Each service instance maintains its own rate limit counters
- **Memory loss on restart**: All rate limit data is lost when the service restarts
- **No horizontal scaling**: Rate limits can be bypassed by hitting different instances

This guide explains how to extend the rate limiter to use distributed storage solutions like Redis, DynamoDB, or other backends.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │     │   Client    │     │   Client    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Service    │     │  Service    │     │  Service    │
│ Instance 1  │     │ Instance 2  │     │ Instance 3  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Redis /   │
                    │  DynamoDB   │
                    └─────────────┘
```

## Implementation Approaches

### 1. Redis-Based Implementation

Redis is the most popular choice for distributed rate limiting due to its:
- High performance and low latency
- Built-in TTL (Time To Live) support
- Atomic operations
- Lua scripting for complex operations

#### Basic Redis Implementation

```python
import redis
import time
from typing import Tuple, Optional
from abc import ABC, abstractmethod

class RateLimitBackend(ABC):
    """Abstract base class for rate limit storage backends."""
    
    @abstractmethod
    async def check_and_update(
        self, 
        key: str, 
        burst: int, 
        rate_per_second: float
    ) -> Tuple[bool, float, float]:
        """Check rate limit and update counter if allowed."""
        pass

class RedisRateLimitBackend(RateLimitBackend):
    """Redis-based rate limit backend using token bucket algorithm."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
    async def check_and_update(
        self, 
        key: str, 
        burst: int, 
        rate_per_second: float
    ) -> Tuple[bool, float, float]:
        """
        Check rate limit using Redis with Lua script for atomicity.
        
        Returns:
            Tuple of (allowed, tokens_remaining, retry_after)
        """
        # Lua script for atomic token bucket implementation
        lua_script = """
        local key = KEYS[1]
        local burst = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(bucket[1]) or burst
        local last_update = tonumber(bucket[2]) or now
        
        -- Calculate new tokens
        local elapsed = now - last_update
        local new_tokens = math.min(tokens + (elapsed * rate), burst)
        
        if new_tokens >= 1 then
            -- Allow request
            new_tokens = new_tokens - 1
            redis.call('HMSET', key, 'tokens', new_tokens, 'last_update', now)
            redis.call('EXPIRE', key, burst / rate + 60)  -- TTL with buffer
            return {1, new_tokens, 0}
        else
            -- Deny request
            local retry_after = (1 - new_tokens) / rate
            return {0, 0, retry_after}
        end
        """
        
        # Execute Lua script
        result = self.redis.eval(
            lua_script, 
            1, 
            key, 
            burst, 
            rate_per_second, 
            time.time()
        )
        
        return (
            bool(result[0]), 
            float(result[1]), 
            float(result[2])
        )
```

#### Integrating with the Middleware

```python
class RateLimiter(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        default_rate_limit_per_minute: int = 60,
        default_rate_limit_burst: int = 10,
        endpoint_limits: Optional[Dict[str, Dict[str, Any]]] = None,
        include_paths: list[str] = None,
        exclude_paths: list[str] = None,
        backend: Optional[RateLimitBackend] = None
    ):
        super().__init__(app)
        # ... existing init code ...
        
        # Use provided backend or fall back to in-memory
        self.backend = backend or InMemoryRateLimitBackend()
        
    async def _check_rate_limit(
        self, 
        bucket_key: Tuple[str, str], 
        burst: int, 
        rate_per_second: float
    ) -> Tuple[bool, float, float]:
        # Convert tuple key to string for backend
        key = f"{bucket_key[0]}:{bucket_key[1]}"
        return await self.backend.check_and_update(key, burst, rate_per_second)
```

### 2. DynamoDB-Based Implementation

For AWS-native applications, DynamoDB can be used with conditional updates:

```python
import boto3
from decimal import Decimal
import time

class DynamoDBRateLimitBackend(RateLimitBackend):
    """DynamoDB-based rate limit backend."""
    
    def __init__(self, table_name: str = "rate_limits"):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
    async def check_and_update(
        self, 
        key: str, 
        burst: int, 
        rate_per_second: float
    ) -> Tuple[bool, float, float]:
        current_time = Decimal(str(time.time()))
        
        try:
            # Try to get existing item
            response = self.table.get_item(Key={'id': key})
            
            if 'Item' in response:
                item = response['Item']
                tokens = float(item['tokens'])
                last_update = float(item['last_update'])
                
                # Calculate new tokens
                elapsed = float(current_time) - last_update
                new_tokens = min(tokens + (elapsed * rate_per_second), burst)
                
                if new_tokens >= 1:
                    # Try to update with conditional check
                    try:
                        self.table.update_item(
                            Key={'id': key},
                            UpdateExpression='SET tokens = :tokens, last_update = :now',
                            ConditionExpression='last_update = :last_update',
                            ExpressionAttributeValues={
                                ':tokens': Decimal(str(new_tokens - 1)),
                                ':now': current_time,
                                ':last_update': Decimal(str(last_update))
                            }
                        )
                        return True, new_tokens - 1, 0
                    except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                        # Another request updated the item, retry
                        return await self.check_and_update(key, burst, rate_per_second)
                else:
                    retry_after = (1 - new_tokens) / rate_per_second
                    return False, 0, retry_after
            else:
                # Create new item
                self.table.put_item(
                    Item={
                        'id': key,
                        'tokens': Decimal(str(burst - 1)),
                        'last_update': current_time,
                        'ttl': int(current_time + (burst / rate_per_second) + 3600)
                    }
                )
                return True, burst - 1, 0
                
        except Exception as e:
            # Log error and fail open (allow request)
            logger.error(f"Rate limit check failed: {e}")
            return True, burst, 0
```

### 3. Memcached Implementation

For simpler deployments, Memcached with atomic increment operations:

```python
import memcache
import json

class MemcachedRateLimitBackend(RateLimitBackend):
    """Memcached-based rate limit backend using sliding window."""
    
    def __init__(self, servers: list = ["127.0.0.1:11211"]):
        self.mc = memcache.Client(servers)
        
    async def check_and_update(
        self, 
        key: str, 
        burst: int, 
        rate_per_second: float
    ) -> Tuple[bool, float, float]:
        window_size = int(burst / rate_per_second)
        current_window = int(time.time() / window_size)
        
        # Use sliding window counter
        window_key = f"{key}:{current_window}"
        
        # Try to increment
        count = self.mc.incr(window_key)
        
        if count is None:
            # Key doesn't exist, create it
            self.mc.set(window_key, 1, time=window_size + 60)
            return True, burst - 1, 0
        
        if count <= burst:
            return True, burst - count, 0
        else:
            # Calculate retry after
            next_window = (current_window + 1) * window_size
            retry_after = next_window - time.time()
            return False, 0, retry_after
```

## Configuration and Deployment

### Environment-Based Configuration

```python
# src/utils/config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Rate limiting backend
    rate_limit_backend: str = "memory"  # memory, redis, dynamodb, memcached
    redis_url: Optional[str] = None
    dynamodb_rate_limit_table: str = "rate_limits"
    memcached_servers: List[str] = ["127.0.0.1:11211"]
```

### Factory Pattern for Backend Selection

```python
# src/api/rate_limit_backends.py
def create_rate_limit_backend(settings: Settings) -> RateLimitBackend:
    """Factory function to create appropriate rate limit backend."""
    
    if settings.rate_limit_backend == "redis":
        if not settings.redis_url:
            raise ValueError("Redis URL required for Redis backend")
        return RedisRateLimitBackend(settings.redis_url)
        
    elif settings.rate_limit_backend == "dynamodb":
        return DynamoDBRateLimitBackend(settings.dynamodb_rate_limit_table)
        
    elif settings.rate_limit_backend == "memcached":
        return MemcachedRateLimitBackend(settings.memcached_servers)
        
    else:
        return InMemoryRateLimitBackend()
```

### Updated Middleware Initialization

```python
# src/main.py
def create_app() -> FastAPI:
    # ... existing code ...
    
    # Create rate limit backend
    rate_limit_backend = create_rate_limit_backend(settings)
    
    # Rate limiting middleware with backend
    app.add_middleware(
        RateLimiter,
        default_rate_limit_per_minute=120,
        default_rate_limit_burst=20,
        include_paths=["/api/"],
        exclude_paths=["/health", "/metrics"],
        backend=rate_limit_backend
    )
```

## Performance Considerations

### 1. Connection Pooling

Always use connection pooling for backend connections:

```python
# Redis with connection pool
redis_pool = redis.ConnectionPool.from_url(
    redis_url,
    max_connections=50,
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)
```

### 2. Async Support

Use async clients for better performance:

```python
import aioredis

class AsyncRedisRateLimitBackend(RateLimitBackend):
    async def __init__(self, redis_url: str):
        self.redis = await aioredis.from_url(redis_url)
```

### 3. Caching and Batching

For high-traffic scenarios, consider:
- Local caching with short TTL
- Batch operations for multiple keys
- Background synchronization

```python
class HybridRateLimitBackend(RateLimitBackend):
    """Hybrid backend with local cache and distributed storage."""
    
    def __init__(self, distributed_backend: RateLimitBackend):
        self.distributed = distributed_backend
        self.local_cache = {}
        self.cache_ttl = 1.0  # 1 second local cache
```

## Monitoring and Observability

### Metrics to Track

```python
from prometheus_client import Counter, Histogram

rate_limit_checks = Counter(
    'rate_limit_checks_total',
    'Total rate limit checks',
    ['backend', 'result']
)

rate_limit_backend_latency = Histogram(
    'rate_limit_backend_latency_seconds',
    'Rate limit backend operation latency',
    ['backend', 'operation']
)
```

### Health Checks

```python
async def rate_limit_health_check():
    """Check rate limit backend health."""
    try:
        test_key = "health_check_test"
        allowed, _, _ = await backend.check_and_update(test_key, 1, 1)
        return {"status": "healthy", "backend": settings.rate_limit_backend}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Testing Distributed Rate Limiting

### Integration Tests

```python
@pytest.mark.asyncio
async def test_distributed_rate_limiting():
    """Test rate limiting across multiple instances."""
    
    # Create multiple app instances with same backend
    backend = RedisRateLimitBackend("redis://localhost:6379")
    
    apps = []
    for i in range(3):
        app = create_test_app(backend=backend)
        apps.append(app)
    
    # Make requests across different instances
    user_token = make_jwt(sub="testuser")
    
    # First two requests should succeed (burst=2)
    for i in range(2):
        app = apps[i % len(apps)]
        async with AsyncClient(transport=ASGITransport(app=app)) as ac:
            resp = await ac.get("/api/test", headers={"Authorization": f"Bearer {user_token}"})
            assert resp.status_code == 200
    
    # Third request should be rate limited on any instance
    app = apps[2]
    async with AsyncClient(transport=ASGITransport(app=app)) as ac:
        resp = await ac.get("/api/test", headers={"Authorization": f"Bearer {user_token}"})
        assert resp.status_code == 429
```

## Migration Strategy

1. **Phase 1**: Deploy with feature flag
   ```python
   if settings.use_distributed_rate_limit:
       backend = create_rate_limit_backend(settings)
   else:
       backend = InMemoryRateLimitBackend()
   ```

2. **Phase 2**: Shadow mode (log differences)
   ```python
   class ShadowRateLimitBackend(RateLimitBackend):
       """Run both backends and compare results."""
   ```

3. **Phase 3**: Gradual rollout
   - Start with non-critical endpoints
   - Monitor performance and accuracy
   - Expand to all endpoints

4. **Phase 4**: Full migration
   - Remove in-memory backend
   - Update documentation
   - Remove feature flags

## Best Practices

1. **Use appropriate TTLs**: Set TTLs on all keys to prevent memory leaks
2. **Handle failures gracefully**: Fail open (allow requests) if backend is unavailable
3. **Monitor backend latency**: Add timeouts and circuit breakers
4. **Use consistent hashing**: For multi-instance Redis/Memcached setups
5. **Regular cleanup**: Implement background jobs to clean expired entries
6. **Test under load**: Ensure the backend can handle your expected traffic

## Conclusion

Extending the rate limiter with distributed storage is essential for production deployments. Choose the backend based on your infrastructure:

- **Redis**: Best for most use cases, excellent performance
- **DynamoDB**: Great for AWS-native applications
- **Memcached**: Simple and effective for basic needs

Remember to monitor performance, handle failures gracefully, and test thoroughly before deploying to production. 