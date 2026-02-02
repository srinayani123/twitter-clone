from fastapi import APIRouter
from app.api import auth, users, tweets, timeline

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(tweets.router, prefix="/tweets", tags=["Tweets"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["Timeline"])
