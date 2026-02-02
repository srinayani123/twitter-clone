import asyncio
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.database import Base, get_db
from app.core.redis import get_redis

# Test database URL (use SQLite for simplicity or PostgreSQL)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class MockRedisClient:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self.data = {}
        self.sorted_sets = {}
        self.sets = {}
    
    async def get(self, key: str):
        return self.data.get(key)
    
    async def set(self, key: str, value: str, ttl: int = None):
        self.data[key] = value
        return True
    
    async def delete(self, key: str):
        if key in self.data:
            del self.data[key]
            return 1
        return 0
    
    async def get_json(self, key: str):
        import json
        value = self.data.get(key)
        return json.loads(value) if value else None
    
    async def set_json(self, key: str, value, ttl: int = None):
        import json
        self.data[key] = json.dumps(value)
        return True
    
    async def zadd(self, key: str, mapping: dict, nx: bool = False):
        if key not in self.sorted_sets:
            self.sorted_sets[key] = {}
        self.sorted_sets[key].update(mapping)
        return len(mapping)
    
    async def zrange(self, key: str, start: int, stop: int, desc: bool = True, withscores: bool = False):
        if key not in self.sorted_sets:
            return []
        items = sorted(self.sorted_sets[key].items(), key=lambda x: x[1], reverse=desc)
        result = items[start:stop + 1 if stop >= 0 else None]
        if withscores:
            return result
        return [item[0] for item in result]
    
    async def zrem(self, key: str, *members):
        count = 0
        if key in self.sorted_sets:
            for member in members:
                if member in self.sorted_sets[key]:
                    del self.sorted_sets[key][member]
                    count += 1
        return count
    
    async def zcard(self, key: str):
        return len(self.sorted_sets.get(key, {}))
    
    async def zremrangebyrank(self, key: str, start: int, stop: int):
        return 0
    
    async def publish(self, channel: str, message: str):
        return 0
    
    async def sadd(self, key: str, *members):
        if key not in self.sets:
            self.sets[key] = set()
        self.sets[key].update(members)
        return len(members)
    
    async def sismember(self, key: str, member: str):
        return member in self.sets.get(key, set())
    
    async def smembers(self, key: str):
        return self.sets.get(key, set())


@pytest.fixture
def mock_redis() -> MockRedisClient:
    """Create a mock Redis client."""
    return MockRedisClient()


@pytest.fixture
async def client(db_session: AsyncSession, mock_redis: MockRedisClient) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden dependencies."""
    
    async def override_get_db():
        yield db_session
    
    async def override_get_redis():
        return mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncGenerator[tuple[AsyncClient, dict], None]:
    """Create a test client with an authenticated user."""
    # Register a user
    register_response = await client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    assert register_response.status_code == 201
    user_data = register_response.json()
    
    # Login to get token
    login_response = await client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123"
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    
    # Set auth header
    client.headers["Authorization"] = f"Bearer {token_data['access_token']}"
    
    yield client, user_data
