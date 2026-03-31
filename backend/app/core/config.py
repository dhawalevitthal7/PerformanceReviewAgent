from pydantic_settings import BaseSettings
import os
import socket


def _resolve_database_url() -> str:
    """
    Return the configured DATABASE_URL, but fall back to local SQLite if the
    PostgreSQL host cannot be resolved (e.g. no internet / Neon project paused).
    This prevents a hard crash on startup during local development.
    """
    url = os.getenv("DATABASE_URL", "sqlite:///./performbharat.db")

    # Only attempt DNS validation for PostgreSQL URLs
    if url.startswith("postgresql"):
        try:
            # Extract hostname from the URL (between @ and the next / or ?)
            host_part = url.split("@")[-1].split("/")[0].split(":")[0]
            socket.getaddrinfo(host_part, None)           # raises if unreachable
        except (socket.gaierror, IndexError):
            print(
                "[WARNING] Could not resolve PostgreSQL host. "
                "Falling back to local SQLite database."
            )
            url = "sqlite:///./performbharat.db"

    return url


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    # Defaults to SQLite for local development.
    # Set DATABASE_URL in your .env file for PostgreSQL (Neon, Supabase…).
    # Example: DATABASE_URL=postgresql://user:password@host:port/dbname
    DATABASE_URL: str = _resolve_database_url()

    # ------------------------------------------------------------------ #
    # JWT / Auth                                                           #
    # ------------------------------------------------------------------ #
    # REQUIRED – generate a strong random string, e.g.:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ------------------------------------------------------------------ #
    # Azure OpenAI                                                         #
    # ------------------------------------------------------------------ #
    # All three values below are REQUIRED. Copy them from the Azure portal.
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
