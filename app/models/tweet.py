from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

class Tweet(Base):
    __tablename__ = "tweets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(String(280), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # For replies
    reply_to_id: Mapped[int] = mapped_column(Integer, ForeignKey("tweets.id"), nullable=True, index=True)
    
    # For retweets with quote
    quote_tweet_id: Mapped[int] = mapped_column(Integer, ForeignKey("tweets.id"), nullable=True)
    
    # Denormalized counts
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    retweets_count: Mapped[int] = mapped_column(Integer, default=0)
    replies_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="tweets")
    replies: Mapped[list["Tweet"]] = relationship("Tweet", backref="parent", remote_side=[id], foreign_keys=[reply_to_id])
    
    # Indexes for timeline queries
    __table_args__ = (
        Index("idx_author_created", "author_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Tweet(id={self.id}, author_id={self.author_id})>"


class Like(Base):
    __tablename__ = "likes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tweet_id: Mapped[int] = mapped_column(Integer, ForeignKey("tweets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_like_user_tweet", "user_id", "tweet_id", unique=True),
    )


class Retweet(Base):
    __tablename__ = "retweets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tweet_id: Mapped[int] = mapped_column(Integer, ForeignKey("tweets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_retweet_user_tweet", "user_id", "tweet_id", unique=True),
    )
