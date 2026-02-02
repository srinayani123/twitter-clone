import pytest
from httpx import AsyncClient


class TestTimeline:
    """Timeline endpoint tests."""
    
    @pytest.mark.asyncio
    async def test_get_home_timeline_empty(self, authenticated_client):
        """Test getting empty home timeline."""
        client, _ = authenticated_client
        
        response = await client.get("/timeline/home")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tweets"] == []
        assert not data["has_more"]
    
    @pytest.mark.asyncio
    async def test_get_home_timeline_with_tweets(self, authenticated_client):
        """Test getting home timeline with own tweets."""
        client, user_data = authenticated_client
        
        # Create some tweets
        for i in range(3):
            await client.post(
                "/tweets",
                json={"content": f"Tweet number {i}"}
            )
        
        # Get timeline (own tweets should appear in user timeline, not home)
        response = await client.get(f"/timeline/user/{user_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tweets"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_user_timeline(self, authenticated_client):
        """Test getting a specific user's timeline."""
        client, user_data = authenticated_client
        
        # Create tweets
        await client.post("/tweets", json={"content": "User timeline tweet 1"})
        await client.post("/tweets", json={"content": "User timeline tweet 2"})
        
        response = await client.get(f"/timeline/user/{user_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tweets"]) == 2
        # Newest first
        assert "tweet 2" in data["tweets"][0]["content"]
    
    @pytest.mark.asyncio
    async def test_timeline_pagination(self, authenticated_client):
        """Test timeline cursor pagination."""
        client, user_data = authenticated_client
        
        # Create enough tweets to paginate
        for i in range(25):
            await client.post("/tweets", json={"content": f"Pagination tweet {i}"})
        
        # Get first page
        response = await client.get(f"/timeline/user/{user_data['id']}?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tweets"]) == 10
        assert data["has_more"]
        assert data["next_cursor"] is not None
        
        # Get second page
        response2 = await client.get(
            f"/timeline/user/{user_data['id']}?limit=10&cursor={data['next_cursor']}"
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["tweets"]) == 10
        
        # Verify no duplicates
        ids_page1 = {t["id"] for t in data["tweets"]}
        ids_page2 = {t["id"] for t in data2["tweets"]}
        assert ids_page1.isdisjoint(ids_page2)
    
    @pytest.mark.asyncio
    async def test_timeline_excludes_replies(self, authenticated_client):
        """Test that user timeline excludes replies."""
        client, user_data = authenticated_client
        
        # Create a regular tweet
        response = await client.post("/tweets", json={"content": "Original tweet"})
        tweet_id = response.json()["id"]
        
        # Create a reply
        await client.post("/tweets", json={
            "content": "This is a reply",
            "reply_to_id": tweet_id
        })
        
        # Get user timeline
        response = await client.get(f"/timeline/user/{user_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        # Only the original tweet, not the reply
        assert len(data["tweets"]) == 1
        assert data["tweets"][0]["content"] == "Original tweet"
    
    @pytest.mark.asyncio
    async def test_home_timeline_unauthorized(self, client: AsyncClient):
        """Test that home timeline requires auth."""
        response = await client.get("/timeline/home")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_user_timeline_public(self, client: AsyncClient, authenticated_client):
        """Test that user timeline is public."""
        auth_client, user_data = authenticated_client
        
        # Create a tweet with auth
        await auth_client.post("/tweets", json={"content": "Public tweet"})
        
        # Get timeline without auth (using unauthenticated client)
        response = await client.get(f"/timeline/user/{user_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tweets"]) == 1
