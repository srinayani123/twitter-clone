from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Follow(Base):
    __tablename__ = "follows"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    follower_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    following_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_follower", "follower_id"),
        Index("idx_following", "following_id"),
        Index("idx_follow_pair", "follower_id", "following_id", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<Follow(follower={self.follower_id}, following={self.following_id})>"
