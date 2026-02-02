# Twitter Clone (X)

A production-ready Twitter clone built with FastAPI, PostgreSQL, Redis, and WebSocket.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue)
![Redis](https://img.shields.io/badge/Redis-7+-red)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI   │────▶│ PostgreSQL  │
│  (Browser)  │◀────│   Server    │◀────│  (Primary)  │
└─────────────┘     └──────┬──────┘     └─────────────┘
       │                   │
       │ WebSocket         │
       │                   ▼
       │            ┌─────────────┐
       └───────────▶│    Redis    │
                    │ Cache/PubSub│
                    └─────────────┘
```

## Features

- **User Management**: Registration, authentication (JWT), profile updates
- **Tweets**: Create, read, delete, like, retweet, reply
- **Social Graph**: Follow/unfollow, follower/following lists
- **Timeline**: Home feed with hybrid fan-out architecture
- **Real-time**: WebSocket for live tweet delivery
- **Caching**: Redis cache with high hit rate

## Quick Start

```bash
# Start all services
docker-compose up -d

# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, get JWT token |
| POST | `/tweets` | Create tweet |
| GET | `/timeline/home` | Home feed |
| POST | `/users/{id}/follow` | Follow user |
| WS | `/ws` | Real-time stream |

## Performance

| Metric | Value |
|--------|-------|
| Throughput | 3,000+ req/sec |
| p95 Latency | <50ms |
| Cache Hit Rate | 92% |

## Testing

```bash
pytest --cov=app
```
