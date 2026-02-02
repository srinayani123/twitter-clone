import pytest
from httpx import AsyncClient


class TestTweets:
    """Tweet endpoint tests."""
    
    @pytest.mark.asyncio
    async def test_create_tweet(self, authenticated_client):
        """Test creating a tweet."""
        client, user_data = authenticated_client
        
        response = await client.post(
            "/tweets",
            json={"content": "Hello, World! This is my first tweet."}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, World! This is my first tweet."
        assert data["author_id"] == user_data["id"]
        assert data["likes_count"] == 0
        assert data["retweets_count"] == 0
    
    @pytest.mark.asyncio
    async def test_create_tweet_too_long(self, authenticated_client):
        """Test creating a tweet that's too long fails."""
        client, _ = authenticated_client
        
        response = await client.post(
            "/tweets",
            json={"content": "x" * 281}  # 281 characters
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_tweet_empty(self, authenticated_client):
        """Test creating an empty tweet fails."""
        client, _ = authenticated_client
        
        response = await client.post(
            "/tweets",
            json={"content": ""}
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_tweet_unauthorized(self, client: AsyncClient):
        """Test creating a tweet without auth fails."""
        response = await client.post(
            "/tweets",
            json={"content": "Unauthorized tweet"}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_tweet(self, authenticated_client):
        """Test getting a tweet by ID."""
        client, user_data = authenticated_client
        
        # Create a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to retrieve"}
        )
        tweet_id = create_response.json()["id"]
        
        # Get the tweet
        response = await client.get(f"/tweets/{tweet_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tweet_id
        assert data["content"] == "Tweet to retrieve"
        assert "author" in data
        assert data["author"]["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_tweet(self, authenticated_client):
        """Test getting a nonexistent tweet returns 404."""
        client, _ = authenticated_client
        
        response = await client.get("/tweets/99999")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_tweet(self, authenticated_client):
        """Test deleting a tweet."""
        client, _ = authenticated_client
        
        # Create a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to delete"}
        )
        tweet_id = create_response.json()["id"]
        
        # Delete the tweet
        response = await client.delete(f"/tweets/{tweet_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = await client.get(f"/tweets/{tweet_id}")
        assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_like_tweet(self, authenticated_client):
        """Test liking a tweet."""
        client, _ = authenticated_client
        
        # Create a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to like"}
        )
        tweet_id = create_response.json()["id"]
        
        # Like the tweet
        response = await client.post(f"/tweets/{tweet_id}/like")
        
        assert response.status_code == 201
        
        # Verify like count increased
        get_response = await client.get(f"/tweets/{tweet_id}")
        assert get_response.json()["likes_count"] == 1
        assert get_response.json()["is_liked"] == True
    
    @pytest.mark.asyncio
    async def test_unlike_tweet(self, authenticated_client):
        """Test unliking a tweet."""
        client, _ = authenticated_client
        
        # Create and like a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to unlike"}
        )
        tweet_id = create_response.json()["id"]
        await client.post(f"/tweets/{tweet_id}/like")
        
        # Unlike the tweet
        response = await client.delete(f"/tweets/{tweet_id}/like")
        
        assert response.status_code == 200
        
        # Verify like count decreased
        get_response = await client.get(f"/tweets/{tweet_id}")
        assert get_response.json()["likes_count"] == 0
        assert get_response.json()["is_liked"] == False
    
    @pytest.mark.asyncio
    async def test_double_like_fails(self, authenticated_client):
        """Test liking a tweet twice fails."""
        client, _ = authenticated_client
        
        # Create a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to double like"}
        )
        tweet_id = create_response.json()["id"]
        
        # Like once
        await client.post(f"/tweets/{tweet_id}/like")
        
        # Like again
        response = await client.post(f"/tweets/{tweet_id}/like")
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_retweet(self, authenticated_client):
        """Test retweeting."""
        client, _ = authenticated_client
        
        # Create a tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Tweet to retweet"}
        )
        tweet_id = create_response.json()["id"]
        
        # Retweet
        response = await client.post(f"/tweets/{tweet_id}/retweet")
        
        assert response.status_code == 201
        
        # Verify retweet count increased
        get_response = await client.get(f"/tweets/{tweet_id}")
        assert get_response.json()["retweets_count"] == 1
        assert get_response.json()["is_retweeted"] == True
    
    @pytest.mark.asyncio
    async def test_reply_to_tweet(self, authenticated_client):
        """Test replying to a tweet."""
        client, _ = authenticated_client
        
        # Create original tweet
        create_response = await client.post(
            "/tweets",
            json={"content": "Original tweet"}
        )
        tweet_id = create_response.json()["id"]
        
        # Reply to it
        reply_response = await client.post(
            "/tweets",
            json={
                "content": "This is a reply",
                "reply_to_id": tweet_id
            }
        )
        
        assert reply_response.status_code == 201
        assert reply_response.json()["reply_to_id"] == tweet_id
        
        # Get replies
        replies_response = await client.get(f"/tweets/{tweet_id}/replies")
        assert replies_response.status_code == 200
        assert len(replies_response.json()) == 1
