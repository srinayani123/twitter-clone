from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.redis import get_redis, RedisClient
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models import User
from app.schemas.tweet import TimelineResponse
from app.services.timeline import TimelineService

router = APIRouter()


@router.get("/home", response_model=TimelineResponse)
async def get_home_timeline(
    cursor: Optional[str] = Query(None, description="Pagination cursor (tweet ID)"),
    limit: int = Query(20, le=100, ge=1),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Get home timeline (tweets from followed users).
    
    Uses cursor-based pagination. Pass the `next_cursor` from the response
    to get the next page of results.
    """
    service = TimelineService(db, redis)
    return await service.get_home_timeline(
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
    )


@router.get("/user/{user_id}", response_model=TimelineResponse)
async def get_user_timeline(
    user_id: int,
    cursor: Optional[str] = Query(None, description="Pagination cursor (tweet ID)"),
    limit: int = Query(20, le=100, ge=1),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get a user's tweets.
    
    Returns tweets posted by the specified user (excludes replies).
    """
    service = TimelineService(db, redis)
    current_user_id = current_user.id if current_user else None
    return await service.get_user_timeline(
        target_user_id=user_id,
        current_user_id=current_user_id,
        limit=limit,
        cursor=cursor,
    )
