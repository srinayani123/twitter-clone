import pytest
from httpx import AsyncClient


class TestAuth:
    """Authentication tests."""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "hashed_password" not in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Test registration with duplicate username fails."""
        # First registration
        await client.post(
            "/auth/register",
            json={
                "username": "duplicateuser",
                "email": "first@example.com",
                "password": "password123"
            }
        )
        
        # Second registration with same username
        response = await client.post(
            "/auth/register",
            json={
                "username": "duplicateuser",
                "email": "second@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post(
            "/auth/register",
            json={
                "username": "validuser",
                "email": "notanemail",
                "password": "password123"
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password fails."""
        response = await client.post(
            "/auth/register",
            json={
                "username": "validuser",
                "email": "valid@example.com",
                "password": "short"
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        # Register first
        await client.post(
            "/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "password123"
            }
        )
        
        # Login
        response = await client.post(
            "/auth/login",
            data={
                "username": "loginuser",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password fails."""
        # Register first
        await client.post(
            "/auth/register",
            json={
                "username": "wrongpassuser",
                "email": "wrong@example.com",
                "password": "correctpassword"
            }
        )
        
        # Login with wrong password
        response = await client.post(
            "/auth/login",
            data={
                "username": "wrongpassuser",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_me(self, authenticated_client):
        """Test getting current user info."""
        client, user_data = authenticated_client
        
        response = await client.get("/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting current user without auth fails."""
        response = await client.get("/auth/me")
        
        assert response.status_code == 401
