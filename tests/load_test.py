"""
Load testing with Locust.

Run with:
    locust -f tests/load_test.py --host=http://localhost:8000

Then open http://localhost:8089 to start the test.
"""

import random
import string
from locust import HttpUser, task, between


def random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase, k=length))


class TwitterUser(HttpUser):
    """Simulates a Twitter user's behavior."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts. Register and login."""
        self.username = f"user_{random_string(8)}"
        self.email = f"{self.username}@example.com"
        self.password = "testpassword123"
        
        # Register
        self.client.post(
            "/auth/register",
            json={
                "username": self.username,
                "email": self.email,
                "password": self.password
            }
        )
        
        # Login
        response = self.client.post(
            "/auth/login",
            data={
                "username": self.username,
                "password": self.password
            }
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}
        
        self.tweet_ids = []
    
    @task(10)
    def get_home_timeline(self):
        """Get home timeline - most common operation."""
        self.client.get("/timeline/home", headers=self.headers)
    
    @task(5)
    def create_tweet(self):
        """Create a new tweet."""
        content = f"Load test tweet {random_string(20)} #{random_string(5)}"
        response = self.client.post(
            "/tweets",
            json={"content": content},
            headers=self.headers
        )
        
        if response.status_code == 201:
            self.tweet_ids.append(response.json()["id"])
    
    @task(3)
    def get_tweet(self):
        """Get a specific tweet."""
        if self.tweet_ids:
            tweet_id = random.choice(self.tweet_ids)
            self.client.get(f"/tweets/{tweet_id}", headers=self.headers)
    
    @task(2)
    def like_tweet(self):
        """Like a tweet."""
        if self.tweet_ids:
            tweet_id = random.choice(self.tweet_ids)
            self.client.post(f"/tweets/{tweet_id}/like", headers=self.headers)
    
    @task(1)
    def follow_user(self):
        """Follow another user (simulated with random ID)."""
        # In a real test, you'd track actual user IDs
        user_id = random.randint(1, 100)
        self.client.post(f"/users/{user_id}/follow", headers=self.headers)
    
    @task(2)
    def get_user_profile(self):
        """Get a user's profile."""
        self.client.get(f"/users/{self.username}", headers=self.headers)


class ReadHeavyUser(HttpUser):
    """User that mostly reads (more realistic for most users)."""
    
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Register and login."""
        self.username = f"reader_{random_string(8)}"
        
        self.client.post(
            "/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@example.com",
                "password": "testpassword123"
            }
        )
        
        response = self.client.post(
            "/auth/login",
            data={
                "username": self.username,
                "password": "testpassword123"
            }
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}
    
    @task(20)
    def get_home_timeline(self):
        """Get home timeline."""
        self.client.get("/timeline/home", headers=self.headers)
    
    @task(5)
    def scroll_timeline(self):
        """Paginate through timeline."""
        response = self.client.get("/timeline/home?limit=20", headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("next_cursor"):
                self.client.get(
                    f"/timeline/home?cursor={data['next_cursor']}&limit=20",
                    headers=self.headers
                )
    
    @task(1)
    def create_tweet(self):
        """Occasionally create a tweet."""
        self.client.post(
            "/tweets",
            json={"content": f"Read-heavy user tweet {random_string(10)}"},
            headers=self.headers
        )
