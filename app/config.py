from pydantic import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database (provide test-friendly defaults; override in real env)
    database_name: str = "test_db"
    database_hostname: str = "localhost"
    database_port: str = "5432"
    database_username: str = "postgres"
    database_password: str = "postgres"

    # Auth/token defaults (non-secret placeholders for CI/tests)
    secret_key: str = "dev-not-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Swagger basic auth (for docs protection)
    swagger_username: str = "test"
    swagger_password: str = "test"

    # OAuth client placeholders (override via env in real deployments)
    google_client_id: str = "dummy-google-client-id"
    google_client_secret: str = "dummy-google-client-secret"
    github_client_id: str = "dummy-github-client-id"
    github_client_secret: str = "dummy-github-client-secret"

    # Frontend base URL used for CORS/redirects
    frontend_url: str = "http://localhost:9001"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


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
