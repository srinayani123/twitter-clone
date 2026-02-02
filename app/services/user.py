from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from app.models import User, Follow
from app.schemas.user import UserUpdate, UserProfile
from app.core.redis import RedisClient


class UserService:
    """User service for profile and follow operations."""
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    
    async def get_profile(self, user_id: int, current_user_id: Optional[int] = None) -> UserProfile:
        """Get user profile with follow status."""
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        is_following = False
        if current_user_id and current_user_id != user_id:
            result = await self.db.execute(
                select(Follow).where(
                    Follow.follower_id == current_user_id,
                    Follow.following_id == user_id
                )
            )
            is_following = result.scalar_one_or_none() is not None
        
        return UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
            followers_count=user.followers_count,
            following_count=user.following_count,
            tweets_count=user.tweets_count,
            is_following=is_following,
            created_at=user.created_at,
        )
    
    async def update_profile(self, user_id: int, data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            await self.db.execute(
                update(User).where(User.id == user_id).values(**update_data)
            )
            await self.db.flush()
            await self.db.refresh(user)
        
        return user
    
    async def follow(self, follower_id: int, following_id: int) -> bool:
        """Follow a user."""
        if follower_id == following_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot follow yourself"
            )
        
        # Check if target user exists
        target = await self.get_by_id(following_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if already following
        result = await self.db.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.following_id == following_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already following this user"
            )
        
        # Create follow relationship
        follow = Follow(follower_id=follower_id, following_id=following_id)
        self.db.add(follow)
        
        # Update counts
        await self.db.execute(
            update(User).where(User.id == follower_id)
            .values(following_count=User.following_count + 1)
        )
        await self.db.execute(
            update(User).where(User.id == following_id)
            .values(followers_count=User.followers_count + 1)
        )
        
        await self.db.flush()
        
        # Invalidate timeline cache
        await self.redis.delete(f"timeline:{follower_id}")
        
        return True
    
    async def unfollow(self, follower_id: int, following_id: int) -> bool:
        """Unfollow a user."""
        result = await self.db.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.following_id == following_id
            )
        )
        follow = result.scalar_one_or_none()
        
        if not follow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not following this user"
            )
        
        await self.db.delete(follow)
        
        # Update counts
        await self.db.execute(
            update(User).where(User.id == follower_id)
            .values(following_count=User.following_count - 1)
        )
        await self.db.execute(
            update(User).where(User.id == following_id)
            .values(followers_count=User.followers_count - 1)
        )
        
        await self.db.flush()
        
        # Invalidate timeline cache
        await self.redis.delete(f"timeline:{follower_id}")
        
        return True
    
    async def get_followers(self, user_id: int, limit: int = 20, offset: int = 0) -> List[User]:
        """Get user's followers."""
        result = await self.db.execute(
            select(User)
            .join(Follow, Follow.follower_id == User.id)
            .where(Follow.following_id == user_id)
            .order_by(Follow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_following(self, user_id: int, limit: int = 20, offset: int = 0) -> List[User]:
        """Get users that user is following."""
        result = await self.db.execute(
            select(User)
            .join(Follow, Follow.following_id == User.id)
            .where(Follow.follower_id == user_id)
            .order_by(Follow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_follower_ids(self, user_id: int) -> List[int]:
        """Get IDs of all followers (for fan-out)."""
        result = await self.db.execute(
            select(Follow.follower_id).where(Follow.following_id == user_id)
        )
        return [row[0] for row in result.fetchall()]
