# Mafia App — Real-Time Multiplayer Game

A backend application for a multiplayer Mafia game, built with **FastAPI**, **PostgreSQL**, and **WebSockets**. The project provides user authentication, game rooms, player management, game rounds, voting, night actions, statistics, and real-time communication.

> **Status:** In development. Some features, access-control rules, and automated tests require further validation before production use.

## Features

- **Authentication** — user registration, JWT-based authentication, token refresh, and Google OAuth integration.
- **Game rooms** — create and manage rooms, join or leave a room, and manage room participants.
- **Game management** — create games, manage game rounds, and handle game phases.
- **Night actions and voting** — backend functionality for player actions and voting mechanics.
- **Real-time communication** — WebSocket-based connections for live game updates and chat.
- **Player profiles** — user information and profile management.
- **Statistics and achievements** — endpoints for game statistics and player achievements.
- **Database migrations** — schema versioning with Alembic.
- **Containerized deployment** — Docker Compose with PostgreSQL and Nginx.

## Tech Stack

| Category                | Technologies                  |
| ----------------------- | ----------------------------- |
| Backend                 | Python, FastAPI               |
| Database                | PostgreSQL                    |
| ORM                     | SQLAlchemy 2.x                |
| Data validation         | Pydantic                      |
| Authentication          | JWT, Passlib, Google OAuth    |
| Real-time communication | WebSockets                    |
| Database migrations     | Alembic                       |
| Deployment              | Docker, Docker Compose, Nginx |
| Testing tools           | pytest, pytest-asyncio        |

## Architecture

The application follows a modular structure, separating API endpoints, database models, schemas, and configuration.

```text
mafia_app/
├── main.py
├── mysite/
│   ├── api/
│   │   ├── auth.py
│   │   ├── friends.py
│   │   ├── game.py
│   │   ├── night_action.py
│   │   ├── room.py
│   │   ├── room_player.py
│   │   ├── statistic.py
│   │   ├── user_profile.py
│   │   └── websocket.py
│   ├── db/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── schema.py
│   ├── admin/
│   └── config.py
├── migrations/
├── nginx/
│   └── nginx.conf
├── Dockerfile
├── docker-compose.yml
└── req.txt
```

### Main components

- `main.py` — initializes the FastAPI application, middleware, API routers, and background scheduler.
- `mysite/api/` — contains endpoints for authentication, rooms, games, player actions, statistics, friends, and WebSockets.
- `mysite/db/models.py` — database models and relationships.
- `mysite/db/schema.py` — Pydantic schemas used for request validation and response serialization.
- `mysite/db/database.py` — SQLAlchemy engine and database session configuration.
- `migrations/` — database migration files managed by Alembic.
- `nginx/` — reverse proxy configuration, including WebSocket support.
- `docker-compose.yml` — defines the application, database, and Nginx services.

## Getting Started

### Prerequisites

Install the following tools:

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Docker Compose
- A Google OAuth client, if you want to test Google authentication

### 1. Clone the repository

```bash
git clone https://github.com/Bakir-developer/mafia_app.git
cd mafia_app
```

### 2. Configure environment variables

Create a `.env` file in the project root. The application expects the following configuration values:

```env
SECRET_KEY=replace_with_a_secure_random_secret
ACCESS_EXPIRE_TOKEN=30
REFRESH_EXPIRE_TOKEN=10080
ALGORITHM=HS256

DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@fast_db:5432/mafia_app

GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:3000
```

**Important:**

- The expiration values above are examples; verify the units expected by the application before using them.
- The Google OAuth redirect URI must match the URI configured in your Google Cloud project and the actual callback route.
- Set the database credentials consistently in `docker-compose.yml` and `DATABASE_URL`.
- Generate a strong secret key and never commit `.env` or real credentials to GitHub.
- The Compose configuration currently contains default PostgreSQL credentials. Replace them before using the application outside a local development environment.

### 3. Start the application

Build and start the containers:

```bash
docker compose up --build
```

The Compose configuration defines three services:

| Service    | Purpose                                |
| ---------- | -------------------------------------- |
| `fast_web` | FastAPI application                    |
| `fast_db`  | PostgreSQL database                    |
| `nginx`    | Reverse proxy and WebSocket forwarding |

The API container waits for the database health check before starting.

### 4. Access the application

With the default Compose ports:

- **API:** [http://localhost:8000](http://localhost:8000)
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Nginx entry point:** [http://localhost:80](http://localhost:80)

The Swagger and ReDoc interfaces are provided by FastAPI. Available endpoints depend on the registered routers and their configuration.

### 5. Database migrations

The project uses Alembic to manage database schema changes.

After verifying the database URL and migration configuration, apply migrations from the application container:

```bash
docker compose exec fast_web alembic upgrade head
```

If the migration environment uses a different database URL from the application, align the configuration before running this command.

### 6. Stop the application

```bash
docker compose down
```

To also delete the PostgreSQL data volume, use:

```bash
docker compose down -v
```

**Warning:** the second command deletes the database volume and its stored data.

## API Overview

The application registers routers for the following areas:

| Area           | Purpose                                             |
| -------------- | --------------------------------------------------- |
| Authentication | Registration, login, token management, Google OAuth |
| User profiles  | User profile operations                             |
| Rooms          | Room creation and management                        |
| Room players   | Room membership                                     |
| Games          | Game and round management                           |
| Night actions  | Night-phase actions, voting, achievements           |
| Friends        | Friend-related operations                           |
| Statistics     | Game and player statistics                          |
| WebSockets     | Real-time connections and chat                      |
| Reviews        | Review-related operations                           |

For the exact HTTP methods, request schemas, and response formats, use the Swagger documentation at `/docs`.

## WebSocket Communication

The project includes a WebSocket connection manager for real-time communication.

Nginx is configured to forward WebSocket upgrade headers and to use extended read and send timeouts for the `/ws/` path.

The exact WebSocket URLs, message formats, and channel permissions should be checked against the implementation in `mysite/api/websocket.py`.

## Testing

The project includes `pytest` and `pytest-asyncio` among its dependencies.

Install the dependencies in a compatible Python environment:

```bash
pip install -r req.txt
```

Run the test suite:

```bash
pytest
```

Automated test coverage has not yet been established. Before relying on the application, add tests for authentication, room permissions, game state transitions, voting rules, night actions, and WebSocket access control.

## Security Considerations

Before deploying this application publicly:

- Enforce authentication and authorization on all protected endpoints.
- Prevent users from assigning themselves privileged roles.
- Validate room membership and game-phase transitions on the server.
- Store secrets in environment variables or a secrets manager.
- Use secure production database credentials.
- Disable development reload mode in production.
- Restrict direct access to the application port when Nginx is intended to be the public entry point.
- Validate OAuth state and avoid transmitting tokens in URL query parameters.
- Add automated tests for unauthorized access and invalid game actions.
- Configure production CORS origins explicitly.

## Roadmap

- [ ] Strengthen authentication and authorization across API endpoints.
- [ ] Validate room capacity and membership rules.
- [ ] Complete and verify game-phase transitions.
- [ ] Improve WebSocket channel permissions and error handling.
- [ ] Add automated unit and integration tests.
- [ ] Add continuous integration with GitHub Actions.
- [ ] Standardize database migrations and environment configuration.
- [ ] Prepare a production deployment configuration.
- [ ] Add screenshots or a short gameplay demonstration.

## Learning Outcomes

This project provides practical experience with:

- Designing REST APIs with FastAPI.
- Modeling relational data with SQLAlchemy and PostgreSQL.
- Implementing JWT authentication and OAuth integration.
- Building real-time features with WebSockets.
- Managing database schema changes with Alembic.
- Containerizing backend services with Docker Compose.
- Configuring Nginx as a reverse proxy.

## Author

**Bakir-developer**
**Mirbekova09**

GitHub: [@Bakir-developer](https://github.com/Bakir-developer)
        [@Mirbekova09](https://github.com/Mirbekova09)

---

*This project is a work in progress. Features and deployment instructions may change as development continues.*
