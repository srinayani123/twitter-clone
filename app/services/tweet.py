from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models import Tweet, Like, Retweet, User
from app.schemas.tweet import TweetCreate, TweetWithAuthor, TweetAuthor
from app.core.redis import RedisClient


class TweetService:
    """Tweet service for CRUD operations."""
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
    
    async def create(self, user_id: int, data: TweetCreate) -> Tweet:
        """Create a new tweet."""
        # Validate reply_to if provided
        if data.reply_to_id:
            parent = await self.get_by_id(data.reply_to_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Reply target tweet not found"
                )
        
        tweet = Tweet(
            content=data.content,
            author_id=user_id,
            reply_to_id=data.reply_to_id,
        )
        
        self.db.add(tweet)
        
        # Update user tweet count
        await self.db.execute(
            update(User).where(User.id == user_id)
            .values(tweets_count=User.tweets_count + 1)
        )
        
        # Update parent reply count if this is a reply
        if data.reply_to_id:
            await self.db.execute(
                update(Tweet).where(Tweet.id == data.reply_to_id)
                .values(replies_count=Tweet.replies_count + 1)
            )
        
        await self.db.flush()
        await self.db.refresh(tweet)
        
        return tweet
    
    async def get_by_id(self, tweet_id: int) -> Optional[Tweet]:
        """Get tweet by ID."""
        result = await self.db.execute(
            select(Tweet)
            .options(selectinload(Tweet.author))
            .where(Tweet.id == tweet_id)
        )
        return result.scalar_one_or_none()
    
    async def get_with_engagement(
        self, 
        tweet_id: int, 
        current_user_id: Optional[int] = None
    ) -> Optional[TweetWithAuthor]:
        """Get tweet with author and engagement status."""
        tweet = await self.get_by_id(tweet_id)
        if not tweet:
            return None
        
        is_liked = False
        is_retweeted = False
        
        if current_user_id:
            # Check like status
            like_result = await self.db.execute(
                select(Like).where(
                    Like.user_id == current_user_id,
                    Like.tweet_id == tweet_id
                )
            )
            is_liked = like_result.scalar_one_or_none() is not None
            
            # Check retweet status
            rt_result = await self.db.execute(
                select(Retweet).where(
                    Retweet.user_id == current_user_id,
                    Retweet.tweet_id == tweet_id
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
    
    async def delete(self, tweet_id: int, user_id: int) -> bool:
        """Delete a tweet."""
        tweet = await self.get_by_id(tweet_id)
        
        if not tweet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tweet not found"
            )
        
        if tweet.author_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete another user's tweet"
            )
        
        # Delete associated likes and retweets
        await self.db.execute(delete(Like).where(Like.tweet_id == tweet_id))
        await self.db.execute(delete(Retweet).where(Retweet.tweet_id == tweet_id))
        
        # Update parent reply count if this is a reply
        if tweet.reply_to_id:
            await self.db.execute(
                update(Tweet).where(Tweet.id == tweet.reply_to_id)
                .values(replies_count=Tweet.replies_count - 1)
            )
        
        # Update user tweet count
        await self.db.execute(
            update(User).where(User.id == user_id)
            .values(tweets_count=User.tweets_count - 1)
        )
        
        await self.db.delete(tweet)
        await self.db.flush()
        
        return True
    
    async def like(self, tweet_id: int, user_id: int) -> bool:
        """Like a tweet."""
        tweet = await self.get_by_id(tweet_id)
        if not tweet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tweet not found"
            )
        
        # Check if already liked
        result = await self.db.execute(
            select(Like).where(Like.user_id == user_id, Like.tweet_id == tweet_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already liked this tweet"
            )
        
        like = Like(user_id=user_id, tweet_id=tweet_id)
        self.db.add(like)
        
        await self.db.execute(
            update(Tweet).where(Tweet.id == tweet_id)
            .values(likes_count=Tweet.likes_count + 1)
        )
        
        await self.db.flush()
        return True
    
    async def unlike(self, tweet_id: int, user_id: int) -> bool:
        """Unlike a tweet."""
        result = await self.db.execute(
            select(Like).where(Like.user_id == user_id, Like.tweet_id == tweet_id)
        )
        like = result.scalar_one_or_none()
        
        if not like:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Haven't liked this tweet"
            )
        
        await self.db.delete(like)
        
        await self.db.execute(
            update(Tweet).where(Tweet.id == tweet_id)
            .values(likes_count=Tweet.likes_count - 1)
        )
        
        await self.db.flush()
        return True
    
    async def retweet(self, tweet_id: int, user_id: int) -> bool:
        """Retweet a tweet."""
        tweet = await self.get_by_id(tweet_id)
        if not tweet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tweet not found"
            )
        
        # Check if already retweeted
        result = await self.db.execute(
            select(Retweet).where(Retweet.user_id == user_id, Retweet.tweet_id == tweet_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already retweeted this tweet"
            )
        
        retweet = Retweet(user_id=user_id, tweet_id=tweet_id)
        self.db.add(retweet)
        
        await self.db.execute(
            update(Tweet).where(Tweet.id == tweet_id)
            .values(retweets_count=Tweet.retweets_count + 1)
        )
        
        await self.db.flush()
        return True
    
    async def unretweet(self, tweet_id: int, user_id: int) -> bool:
        """Undo a retweet."""
        result = await self.db.execute(
            select(Retweet).where(Retweet.user_id == user_id, Retweet.tweet_id == tweet_id)
        )
        retweet = result.scalar_one_or_none()
        
        if not retweet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Haven't retweeted this tweet"
            )
        
        await self.db.delete(retweet)
        
        await self.db.execute(
            update(Tweet).where(Tweet.id == tweet_id)
            .values(retweets_count=Tweet.retweets_count - 1)
        )
        
        await self.db.flush()
        return True
    
    async def get_replies(
        self, 
        tweet_id: int, 
        limit: int = 20, 
        offset: int = 0,
        current_user_id: Optional[int] = None
    ) -> List[TweetWithAuthor]:
        """Get replies to a tweet."""
        result = await self.db.execute(
            select(Tweet)
            .options(selectinload(Tweet.author))
            .where(Tweet.reply_to_id == tweet_id)
            .order_by(Tweet.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        tweets = result.scalars().all()
        
        return [
            await self._enrich_tweet(tweet, current_user_id)
            for tweet in tweets
        ]
    
    async def _enrich_tweet(
        self, 
        tweet: Tweet, 
        current_user_id: Optional[int]
    ) -> TweetWithAuthor:
        """Add engagement data to tweet."""
        is_liked = False
        is_retweeted = False
        
        if current_user_id:
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
