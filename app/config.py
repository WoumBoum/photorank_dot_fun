from pydantic import BaseSettings


class Settings(BaseSettings):
    # Comma-separated list of user IDs to treat as alts
    alt_user_ids = __import__("os").getenv("ALT_USER_IDS", "")
    # Database (provide test-friendly defaults; override in real env)
    database_url = __import__("os").getenv("DATABASE_URL")
    database_name = "test_db"
    database_hostname = "localhost"
    database_port = "5432"
    database_username = "postgres"
    database_password = "postgres"

    # Auth/token defaults (non-secret placeholders for CI/tests)
    secret_key = "dev-not-secret"
    algorithm = "HS256"
    access_token_expire_minutes = 30

    # Swagger basic auth (for docs protection)
    swagger_username = "test"
    swagger_password = "test"

    # OAuth client placeholders (override via env in real deployments)
    google_client_id = "dummy-google-client-id"
    google_client_secret = "dummy-google-client-secret"
    github_client_id = "dummy-github-client-id"
    github_client_secret = "dummy-github-client-secret"

    # Frontend base URL used for CORS/redirects
    frontend_url = __import__("os").getenv("FRONTEND_URL", "http://localhost:9001")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

title = "Social media app with FastAPI"
description = """
\nThis project provides a complete REST API using Python 3\n
"""
tags_metadata = [
    {
        "name": "Root",
        "description": "Root description",
    },
    {
        "name": "Posts",
        "description": "Posts description",
    },
    {
        "name": "Users",
        "description": "Users description",
    },
    {
        "name": "Authentication",
        "description": "Authentication description",
    },
    {
        "name": "Vote",
        "description": "Vote description",
    }
]
