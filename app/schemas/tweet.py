from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class TweetAuthor(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    
    class Config:
        from_attributes = True


class TweetCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=280)
    reply_to_id: Optional[int] = None


class TweetResponse(BaseModel):
    id: int
    content: str
    author_id: int
    reply_to_id: Optional[int] = None
    likes_count: int = 0
    retweets_count: int = 0
    replies_count: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True


class TweetWithAuthor(TweetResponse):
    author: TweetAuthor
    is_liked: bool = False      # Whether current user liked this tweet
    is_retweeted: bool = False  # Whether current user retweeted this tweet


class TimelineResponse(BaseModel):
    tweets: List[TweetWithAuthor]
    next_cursor: Optional[str] = None
    has_more: bool = False
