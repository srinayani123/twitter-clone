"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('followers_count', sa.Integer(), default=0),
        sa.Column('following_count', sa.Integer(), default=0),
        sa.Column('tweets_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Tweets table
    op.create_table(
        'tweets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(280), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('reply_to_id', sa.Integer(), nullable=True),
        sa.Column('quote_tweet_id', sa.Integer(), nullable=True),
        sa.Column('likes_count', sa.Integer(), default=0),
        sa.Column('retweets_count', sa.Integer(), default=0),
        sa.Column('replies_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reply_to_id'], ['tweets.id']),
        sa.ForeignKeyConstraint(['quote_tweet_id'], ['tweets.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tweets_id', 'tweets', ['id'])
    op.create_index('ix_tweets_author_id', 'tweets', ['author_id'])
    op.create_index('ix_tweets_reply_to_id', 'tweets', ['reply_to_id'])
    op.create_index('ix_tweets_created_at', 'tweets', ['created_at'])
    op.create_index('idx_author_created', 'tweets', ['author_id', 'created_at'])
    
    # Follows table
    op.create_table(
        'follows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('follower_id', sa.Integer(), nullable=False),
        sa.Column('following_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id']),
        sa.ForeignKeyConstraint(['following_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_follows_id', 'follows', ['id'])
    op.create_index('idx_follower', 'follows', ['follower_id'])
    op.create_index('idx_following', 'follows', ['following_id'])
    op.create_index('idx_follow_pair', 'follows', ['follower_id', 'following_id'], unique=True)
    
    # Likes table
    op.create_table(
        'likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tweet_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tweet_id'], ['tweets.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_likes_id', 'likes', ['id'])
    op.create_index('idx_like_user_tweet', 'likes', ['user_id', 'tweet_id'], unique=True)
    
    # Retweets table
    op.create_table(
        'retweets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tweet_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tweet_id'], ['tweets.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_retweets_id', 'retweets', ['id'])
    op.create_index('idx_retweet_user_tweet', 'retweets', ['user_id', 'tweet_id'], unique=True)


def downgrade() -> None:
    op.drop_table('retweets')
    op.drop_table('likes')
    op.drop_table('follows')
    op.drop_table('tweets')
    op.drop_table('users')
