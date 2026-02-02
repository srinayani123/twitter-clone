from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.redis import get_redis, RedisClient
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models import User
from app.schemas.tweet import TweetCreate, TweetResponse, TweetWithAuthor
from app.services.tweet import TweetService
from app.services.fanout import FanoutService

router = APIRouter()


@router.post("", response_model=TweetResponse, status_code=status.HTTP_201_CREATED)
async def create_tweet(
    data: TweetCreate,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Create a new tweet."""
    tweet_service = TweetService(db, redis)
    tweet = await tweet_service.create(current_user.id, data)
    
    # Fan-out to followers
    fanout_service = FanoutService(db, redis)
    await fanout_service.fanout_tweet(tweet, current_user)
    
    return tweet


@router.get("/{tweet_id}", response_model=TweetWithAuthor)
async def get_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get a single tweet."""
    service = TweetService(db, redis)
    current_user_id = current_user.id if current_user else None
    tweet = await service.get_with_engagement(tweet_id, current_user_id)
    
    if not tweet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tweet not found"
        )
    
    return tweet


@router.delete("/{tweet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Delete a tweet."""
    service = TweetService(db, redis)
    tweet = await service.get_by_id(tweet_id)
    
    if tweet:
        # Remove from timelines
        fanout_service = FanoutService(db, redis)
        await fanout_service.remove_from_timelines(tweet, current_user)
    
    await service.delete(tweet_id, current_user.id)


@router.post("/{tweet_id}/like", status_code=status.HTTP_201_CREATED)
async def like_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Like a tweet."""
    service = TweetService(db, redis)
    await service.like(tweet_id, current_user.id)
    return {"message": "Tweet liked"}


@router.delete("/{tweet_id}/like")
async def unlike_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Unlike a tweet."""
    service = TweetService(db, redis)
    await service.unlike(tweet_id, current_user.id)
    return {"message": "Tweet unliked"}


@router.post("/{tweet_id}/retweet", status_code=status.HTTP_201_CREATED)
async def retweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Retweet a tweet."""
    service = TweetService(db, redis)
    await service.retweet(tweet_id, current_user.id)
    return {"message": "Retweeted"}


@router.delete("/{tweet_id}/retweet")
async def unretweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Undo a retweet."""
    service = TweetService(db, redis)
    await service.unretweet(tweet_id, current_user.id)
    return {"message": "Unretweet successful"}


@router.get("/{tweet_id}/replies", response_model=List[TweetWithAuthor])
async def get_replies(
    tweet_id: int,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get replies to a tweet."""
    service = TweetService(db, redis)
    current_user_id = current_user.id if current_user else None
    return await service.get_replies(tweet_id, limit, offset, current_user_id)
