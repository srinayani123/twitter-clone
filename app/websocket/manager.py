import json
import asyncio
from typing import Dict, Set, Optional
from fastapi import WebSocket
from app.core.redis import redis_client


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._pubsub_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        
        # Start pub/sub listener if not running
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(self._listen_to_redis())
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user's connections."""
        if user_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.add(websocket)
            
            # Clean up disconnected sockets
            for ws in disconnected:
                self.active_connections[user_id].discard(ws)
    
    async def broadcast(self, message: dict, user_ids: list[int]):
        """Broadcast a message to multiple users."""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
    
    async def _listen_to_redis(self):
        """Listen to Redis pub/sub for real-time events."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("tweets:realtime")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._handle_realtime_event(data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Redis pub/sub error: {e}")
        finally:
            await pubsub.unsubscribe("tweets:realtime")
    
    async def _handle_realtime_event(self, event: dict):
        """Handle incoming real-time events."""
        event_type = event.get("type")
        
        if event_type == "new_tweet":
            # Broadcast new tweet to relevant followers
            follower_ids = event.get("follower_ids", [])
            message = {
                "type": "new_tweet",
                "tweet_id": event.get("tweet_id"),
                "author_id": event.get("author_id"),
                "content": event.get("content"),
            }
            await self.broadcast(message, follower_ids)
        
        elif event_type == "tweet_deleted":
            # Broadcast deletion to all connected users
            message = {
                "type": "tweet_deleted",
                "tweet_id": event.get("tweet_id"),
            }
            for user_id in list(self.active_connections.keys()):
                await self.send_personal_message(message, user_id)
    
    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())
    
    @property
    def user_count(self) -> int:
        """Get number of connected users."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()
