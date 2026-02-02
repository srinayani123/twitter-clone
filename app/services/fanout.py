import json
import asyncio
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Tweet, User, Follow
from app.core.redis import RedisClient
from app.config import settings


class FanoutService:
    """Handles fan-out of tweets to follower timelines.
    
    Strategy:
    - For users with < 5K followers: Fan-out on write (push to all follower timelines)
    - For users with >= 5K followers: Fan-out on read (store in celebrity cache)
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
    
    async def fanout_tweet(self, tweet: Tweet, author: User) -> int:
        """Fan out a new tweet to followers.
        
        Returns the number of timelines updated.
        """
        if author.followers_count >= settings.celebrity_threshold:
            # Celebrity: store in their dedicated cache
            return await self._fanout_celebrity(tweet, author)
        else:
            # Regular user: push to all follower timelines
            return await self._fanout_regular(tweet, author)
    
    async def _fanout_regular(self, tweet: Tweet, author: User) -> int:
        """Fan-out on write for regular users."""
        # Get all follower IDs
        result = await self.db.execute(
            select(Follow.follower_id).where(Follow.following_id == author.id)
        )
        follower_ids = [row[0] for row in result.fetchall()]
        
        if not follower_ids:
            return 0
        
        # Push to each follower's timeline cache
        # Using pipeline for efficiency
        count = 0
        for follower_id in follower_ids:
            cache_key = f"timeline:{follower_id}"
            
            # Add tweet to sorted set (score = tweet ID for ordering)
            await self.redis.zadd(cache_key, {str(tweet.id): float(tweet.id)})
            
            # Trim to max size to prevent unbounded growth
            await self.redis.zremrangebyrank(cache_key, 0, -settings.timeline_max_size - 1)
            
            count += 1
        
        # Also publish to real-time channel
        await self._publish_realtime(tweet, follower_ids)
        
        return count
    
    async def _fanout_celebrity(self, tweet: Tweet, author: User) -> int:
        """Fan-out on read for celebrities - store in dedicated cache."""
        cache_key = f"celebrity_tweets:{author.id}"
        
        # Add to celebrity's tweet cache
        await self.redis.zadd(cache_key, {str(tweet.id): float(tweet.id)})
        
        # Keep only recent tweets (e.g., last 200)
        await self.redis.zremrangebyrank(cache_key, 0, -201)
        
        # Set TTL
        await self.redis.redis.expire(cache_key, settings.timeline_cache_ttl * 2)
        
        # Publish to real-time channel for connected followers
        result = await self.db.execute(
            select(Follow.follower_id).where(Follow.following_id == author.id)
        )
        follower_ids = [row[0] for row in result.fetchall()]
        await self._publish_realtime(tweet, follower_ids)
        
        return 1  # Only updated one cache entry
    
    async def _publish_realtime(self, tweet: Tweet, follower_ids: List[int]):
        """Publish tweet to real-time WebSocket channel."""
        message = json.dumps({
            "type": "new_tweet",
            "tweet_id": tweet.id,
            "author_id": tweet.author_id,
            "content": tweet.content,
            "follower_ids": follower_ids,
        })
        
        await self.redis.publish("tweets:realtime", message)
    
    async def remove_from_timelines(self, tweet: Tweet, author: User):
        """Remove a deleted tweet from all timelines."""
        if author.followers_count >= settings.celebrity_threshold:
            # Remove from celebrity cache
            cache_key = f"celebrity_tweets:{author.id}"
            await self.redis.zrem(cache_key, str(tweet.id))
        else:
            # Remove from follower timelines
            result = await self.db.execute(
                select(Follow.follower_id).where(Follow.following_id == author.id)
            )
            follower_ids = [row[0] for row in result.fetchall()]
            
            for follower_id in follower_ids:
                cache_key = f"timeline:{follower_id}"
                await self.redis.zrem(cache_key, str(tweet.id))
        
        # Publish deletion event
        message = json.dumps({
            "type": "tweet_deleted",
            "tweet_id": tweet.id,
        })
        await self.redis.publish("tweets:realtime", message)
