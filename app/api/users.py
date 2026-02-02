from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.redis import get_redis, RedisClient
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models import User
from app.schemas.user import UserResponse, UserUpdate, UserProfile
from app.services.user import UserService

router = APIRouter()


@router.get("/{username}", response_model=UserProfile)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get a user's public profile."""
    service = UserService(db, redis)
    user = await service.get_by_username(username)
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    current_user_id = current_user.id if current_user else None
    return await service.get_profile(user.id, current_user_id)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile."""
    service = UserService(db, redis)
    return await service.update_profile(current_user.id, data)


@router.post("/{user_id}/follow")
async def follow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Follow a user."""
    service = UserService(db, redis)
    await service.follow(current_user.id, user_id)
    return {"message": "Successfully followed user"}


@router.delete("/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """Unfollow a user."""
    service = UserService(db, redis)
    await service.unfollow(current_user.id, user_id)
    return {"message": "Successfully unfollowed user"}


@router.get("/{user_id}/followers", response_model=List[UserResponse])
async def get_followers(
    user_id: int,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get a user's followers."""
    service = UserService(db, redis)
    return await service.get_followers(user_id, limit, offset)


@router.get("/{user_id}/following", response_model=List[UserResponse])
async def get_following(
    user_id: int,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get users that a user is following."""
    service = UserService(db, redis)
    return await service.get_following(user_id, limit, offset)
