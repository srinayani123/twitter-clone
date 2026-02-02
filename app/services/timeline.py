from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Tweet, User, Follow, Like, Retweet
from app.schemas.tweet import TweetWithAuthor, TweetAuthor, TimelineResponse
from app.core.redis import RedisClient
from app.config import settings


class TimelineService:
    """Timeline service with hybrid fan-out architecture.
    
    Uses fan-out on write for regular users (<5K followers)
    Uses fan-out on read for celebrities (>5K followers)
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
    
    async def get_home_timeline(
        self,
        user_id: int,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> TimelineResponse:
        """Get home timeline for a user.
        
        Combines:
        1. Cached timeline (fan-out on write results)
        2. Celebrity tweets (fan-out on read)
        """
        # Try to get from cache first
        cache_key = f"timeline:{user_id}"
        cached_tweet_ids = await self.redis.zrange(cache_key, 0, limit + 50, desc=True)
        
        # Get celebrity tweets that user follows
        celebrity_tweet_ids = await self._get_celebrity_tweets(user_id, limit)
        
        # Merge and dedupe
        all_tweet_ids = list(set(cached_tweet_ids + celebrity_tweet_ids))
        
        if not all_tweet_ids:
            # Cache miss or empty - rebuild from database
            all_tweet_ids = await self._rebuild_timeline(user_id, limit * 2)
        
        # Parse cursor for pagination
        max_id = None
        if cursor:
            try:
                max_id = int(cursor)
            except ValueError:
                pass
        
        # Filter by cursor
        if max_id:
            all_tweet_ids = [tid for tid in all_tweet_ids if int(tid) < max_id]
        
        # Sort by ID (descending = newest first)
        all_tweet_ids = sorted(all_tweet_ids, key=lambda x: int(x), reverse=True)[:limit + 1]
        
        # Check if there are more
        has_more = len(all_tweet_ids) > limit
        if has_more:
            all_tweet_ids = all_tweet_ids[:limit]
        
        # Fetch actual tweets
        tweets = await self._fetch_tweets(all_tweet_ids, user_id)
        
        # Generate next cursor
        next_cursor = None
        if has_more and tweets:
            next_cursor = str(tweets[-1].id)
        
        return TimelineResponse(
            tweets=tweets,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    
    async def get_user_timeline(
        self,
        target_user_id: int,
        current_user_id: Optional[int] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> TimelineResponse:
        """Get a user's tweets."""
        # Parse cursor
        max_id = None
        if cursor:
            try:
                max_id = int(cursor)
            except ValueError:
                pass
        
        # Build query
        query = (
            select(Tweet)
            .options(selectinload(Tweet.author))
            .where(Tweet.author_id == target_user_id)
            .where(Tweet.reply_to_id.is_(None))  # Exclude replies
            .order_by(Tweet.id.desc())
            .limit(limit + 1)
        )
        
        if max_id:
            query = query.where(Tweet.id < max_id)
        
        result = await self.db.execute(query)
        tweets = list(result.scalars().all())
        
        has_more = len(tweets) > limit
        if has_more:
            tweets = tweets[:limit]
        
        # Enrich with engagement data
        enriched = [
            await self._enrich_tweet(tweet, current_user_id)
            for tweet in tweets
        ]
        
        next_cursor = None
        if has_more and enriched:
            next_cursor = str(enriched[-1].id)
        
        return TimelineResponse(
            tweets=enriched,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    
    async def _get_celebrity_tweets(self, user_id: int, limit: int) -> List[str]:
        """Get recent tweets from celebrities the user follows."""
        # Find celebrities user follows
        result = await self.db.execute(
            select(User.id)
            .join(Follow, Follow.following_id == User.id)
            .where(Follow.follower_id == user_id)
            .where(User.followers_count >= settings.celebrity_threshold)
        )
        celebrity_ids = [row[0] for row in result.fetchall()]
        
        if not celebrity_ids:
            return []
        
        # Get their recent tweets
        tweet_ids = []
        for celeb_id in celebrity_ids:
            cache_key = f"celebrity_tweets:{celeb_id}"
            ids = await self.redis.zrange(cache_key, 0, limit, desc=True)
            tweet_ids.extend(ids)
        
        return tweet_ids
    
    async def _rebuild_timeline(self, user_id: int, limit: int) -> List[str]:
        """Rebuild timeline from database (cache miss)."""
        # Get users this user follows
        result = await self.db.execute(
            select(Follow.following_id).where(Follow.follower_id == user_id)
        )
        following_ids = [row[0] for row in result.fetchall()]
        
        if not following_ids:
            return []
        
        # Get their recent tweets
        result = await self.db.execute(
            select(Tweet.id)
            .where(Tweet.author_id.in_(following_ids))
            .where(Tweet.reply_to_id.is_(None))
            .order_by(Tweet.id.desc())
            .limit(limit)
        )
        tweet_ids = [str(row[0]) for row in result.fetchall()]
        
        # Repopulate cache
        if tweet_ids:
            cache_key = f"timeline:{user_id}"
            for tweet_id in tweet_ids:
                await self.redis.zadd(cache_key, {tweet_id: float(tweet_id)})
            # Set TTL
            await self.redis.redis.expire(cache_key, settings.timeline_cache_ttl)
        
        return tweet_ids
    
    async def _fetch_tweets(
        self, 
        tweet_ids: List[str], 
        current_user_id: int
    ) -> List[TweetWithAuthor]:
        """Fetch tweets by IDs and enrich with engagement data."""
        if not tweet_ids:
            return []
        
        int_ids = [int(tid) for tid in tweet_ids]
        
        result = await self.db.execute(
            select(Tweet)
            .options(selectinload(Tweet.author))
            .where(Tweet.id.in_(int_ids))
        )
        tweets = {tweet.id: tweet for tweet in result.scalars().all()}
        
        # Maintain order and enrich
        enriched = []
        for tid in int_ids:
            tweet = tweets.get(tid)
            if tweet:
                enriched.append(await self._enrich_tweet(tweet, current_user_id))
        
        return enriched
    
    async def _enrich_tweet(
        self, 
        tweet: Tweet, 
        current_user_id: Optional[int]
    ) -> TweetWithAuthor:
        """Add engagement data to tweet."""
        is_liked = False
        is_retweeted = False
        
        if current_user_id:
            # Batch these queries in production for better performance
            like_result = await self.db.execute(
                select(Like).where(
                    Like.user_id == current_user_id,
                    Like.tweet_id == tweet.id
                )
            )
            is_liked = like_result.scalar_one_or_none() is not None
            
            rt_result = await self.db.execute(
                select(Retweet).where(
                    Retweet.user_id == current_user_id,
                    Retweet.tweet_id == tweet.id
                )
            )
            is_retweeted = rt_result.scalar_one_or_none() is not None
        
        return TweetWithAuthor(
            id=tweet.id,
            content=tweet.content,
            author_id=tweet.author_id,
            reply_to_id=tweet.reply_to_id,
            likes_count=tweet.likes_count,
            retweets_count=tweet.retweets_count,
            replies_count=tweet.replies_count,
            created_at=tweet.created_at,
            author=TweetAuthor(
                id=tweet.author.id,
                username=tweet.author.username,
                display_name=tweet.author.display_name,
                avatar_url=tweet.author.avatar_url,
                is_verified=tweet.author.is_verified,
            ),
            is_liked=is_liked,
            is_retweeted=is_retweeted,
        )
