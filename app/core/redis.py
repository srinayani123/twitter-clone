import json
from typing import Optional, List, Any
from redis import asyncio as aioredis
from app.config import settings


class RedisClient:
    """Redis client wrapper with connection pooling."""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection."""
        self.redis = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
    
    # String operations
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis."""
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, ttl: int = None) -> bool:
        """Set a value in Redis with optional TTL."""
        if ttl:
            return await self.redis.setex(key, ttl, value)
        return await self.redis.set(key, value)
    
    async def delete(self, key: str) -> int:
        """Delete a key from Redis."""
        return await self.redis.delete(key)
    
    # JSON operations
    async def get_json(self, key: str) -> Optional[Any]:
        """Get and parse JSON from Redis."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(self, key: str, value: Any, ttl: int = None) -> bool:
        """Serialize and store JSON in Redis."""
        return await self.set(key, json.dumps(value), ttl)
    
    # Sorted set operations (for timelines)
    async def zadd(self, key: str, mapping: dict, nx: bool = False) -> int:
        """Add members to a sorted set."""
        return await self.redis.zadd(key, mapping, nx=nx)
    
    async def zrange(self, key: str, start: int, stop: int, desc: bool = True, withscores: bool = False) -> List:
        """Get range from sorted set."""
        if desc:
            return await self.redis.zrevrange(key, start, stop, withscores=withscores)
        return await self.redis.zrange(key, start, stop, withscores=withscores)
    
    async def zrem(self, key: str, *members) -> int:
        """Remove members from sorted set."""
        return await self.redis.zrem(key, *members)
    
    async def zcard(self, key: str) -> int:
        """Get cardinality of sorted set."""
        return await self.redis.zcard(key)
    
    async def zremrangebyrank(self, key: str, start: int, stop: int) -> int:
        """Remove elements by rank range."""
        return await self.redis.zremrangebyrank(key, start, stop)
    
    # Pub/Sub for real-time
    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel."""
        return await self.redis.publish(channel, message)
    
    def pubsub(self):
        """Get pub/sub instance."""
        return self.redis.pubsub()
    
    # Set operations (for tracking)
    async def sadd(self, key: str, *members) -> int:
        """Add members to set."""
        return await self.redis.sadd(key, *members)
    
    async def sismember(self, key: str, member: str) -> bool:
        """Check if member exists in set."""
        return await self.redis.sismember(key, member)
    
    async def smembers(self, key: str) -> set:
        """Get all members of set."""
        return await self.redis.smembers(key)
    
    async def srem(self, key: str, *members) -> int:
        """Remove members from set."""
        return await self.redis.srem(key, *members)


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency for getting Redis client."""
    return redis_client
