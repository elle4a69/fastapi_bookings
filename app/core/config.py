"""Application configuration settings.

This module defines the :class:`Settings` class which centralizes
configuration for the FastAPI Bookings project. Settings are loaded
from environment variables where available and fall back to sensible
defaults otherwise. See the documentation for details on how these
values are used throughout the application.
"""

# BaseSettings moved to pydantic_settings in Pydantic v2
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback for environments with Pydantic v1
    from pydantic import BaseSettings
    SettingsConfigDict = dict
from typing import List, Optional
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """Application configuration.

    Values can be overridden using environment variables. When
    referencing settings in other modules, import the global ``settings``
    instance defined at the bottom of this file.
    """

    # Environment and project
    APP_ENV: str = Field("development", description="Application environment")
    PROJECT_NAME: str = Field("FastAPI Bookings", description="Project name")

    # Database
    DATABASE_URL: str = Field(
        "sqlite:///./fastapi_bookings.db",
        description="Database connection URL",
    )
    ASYNC_DATABASE_URL: str | None = Field(
        None,
        description="Async database connection URL (defaults to asyncpg/aiosqlite converted from DATABASE_URL)",
    )
    DB_POOL_SIZE: int = Field(10, description="PostgreSQL connection pool size")
    DB_MAX_OVERFLOW: int = Field(20, description="PostgreSQL connection pool max overflow")
    DB_POOL_TIMEOUT: int = Field(30, description="PostgreSQL connection pool timeout seconds")
    DB_POOL_RECYCLE: int = Field(1800, description="PostgreSQL connection recycle seconds (30m)")

    # Redis
    REDIS_URL: str = Field(
        "redis://127.0.0.1:6380/0",
        description="Redis connection URL for caching, rate limiting, and ephemeral state",
    )

    @property
    def async_database_url(self) -> str:
        """Derive the async database connection string."""
        if self.ASYNC_DATABASE_URL:
            return self.ASYNC_DATABASE_URL
        url = self.DATABASE_URL
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if url.startswith("sqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    # Security
    SECRET_KEY: str = Field(
        "changeme",
        description="Secret key used to sign JWT tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60 * 24 * 7,
        description="Number of minutes an access token is valid",
    )
    # Public API key for client tokens
    PUBLIC_API_KEY: str = Field(
        "local-public-key-change-me",
        description="API key used by the public widget to obtain a token",
    )

    # Frontend
    FRONTEND_ORIGINS: str = Field(
        "",
        description="Comma separated list of allowed origins for CORS",
    )
    WIDGET_SCRIPT_URL: str = Field(
        "/static/booking-widget.js",
        description="URL used in generated booking-form embed metadata",
    )

    # ClickSend SMS/MMS Settings
    CLICKSEND_API_USERNAME: str = Field("", description="ClickSend API username")
    CLICKSEND_API_KEY: str = Field("", description="ClickSend API key")

    # Stripe Settings
    STRIPE_PUBLISHABLE_KEY: str = Field("", description="Stripe Publishable Key")
    STRIPE_SECRET_KEY: str = Field("", description="Stripe Secret Key")
    STRIPE_WEBHOOK_SECRET: str = Field("", description="Stripe Webhook Secret")

    # Firebase Settings
    FIREBASE_CREDENTIALS_JSON: str = Field("", description="Firebase Service Account JSON string or filepath")

    # Mapbox Settings
    MAPBOX_ACCESS_TOKEN: str = Field("", description="Mapbox Access Token")

    # OpenAI Settings
    OPENAI_API_KEY: str = Field("", description="OpenAI API Key")

    # Cal.com Settings
    CALCOM_API_KEY: str = Field("", description="Cal.com API key")
    CALCOM_BASE_URL: str = Field("https://api.cal.com/v1", description="Cal.com API base URL")

    # OSRM Settings
    OSRM_BASE_URL: str = Field("https://router.project-osrm.org", description="OSRM routing base URL")

    # Chatwoot Settings
    CHATWOOT_BASE_URL: str = Field("https://app.chatwoot.com", description="Chatwoot base URL")
    CHATWOOT_API_ACCESS_TOKEN: str = Field("", description="Chatwoot API access token")
    CHATWOOT_WEBHOOK_SECRET: str = Field("", description="Chatwoot webhook secret")

    # Outbox settings
    OUTBOX_POLL_INTERVAL: float = Field(5.0, description="Outbox worker polling interval in seconds")
    OUTBOX_MAX_RETRIES: int = Field(5, ge=1, le=100, description="Maximum attempts snapshotted on new outbox events")
    OUTBOX_LEASE_SECONDS: int = Field(120, ge=30, description="Generic outbox claim lease duration")
    OUTBOX_SHUTDOWN_GRACE_SECONDS: float = Field(30.0, ge=0.1, description="Worker in-flight shutdown grace period")
    OUTBOX_BATCH_SIZE: int = Field(20, ge=1, le=100, description="Maximum events handled per poll")
    OUTBOX_RETRY_BASE_SECONDS: float = Field(5.0, ge=0.1, description="Initial outbox retry delay")
    OUTBOX_RETRY_MAX_SECONDS: float = Field(300.0, ge=1.0, description="Maximum outbox retry delay")
    OUTBOX_RETRY_JITTER_RATIO: float = Field(0.2, ge=0.0, le=1.0, description="Bounded outbox retry jitter")

    # OpenTelemetry / observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        "http://localhost:4318", description="OTLP exporter base endpoint URL"
    )
    OTEL_SDK_DISABLED: bool = Field(
        False, description="Set to True to disable OTel SDK"
    )

    # Neo4j & Graph Knowledge Settings
    NEO4J_URI: str = Field("bolt://127.0.0.1:7687", description="Neo4j connection URI")
    NEO4J_USER: str = Field("neo4j", description="Neo4j username")
    NEO4J_PASSWORD: str = Field("bookings_dev_neo4j_password", description="Neo4j password")
    NEO4J_DATABASE: str = Field("neo4j", description="Neo4j database name")
    GRAPH_KNOWLEDGE_ENABLED: bool = Field(True, description="Enable live Graphiti / KnowledgeGateway retrieval")
    GRAPH_SHADOW_WRITE: bool = Field(True, description="Enable shadow writing of accepted knowledge to Graphiti")
    GRAPH_SHADOW_READ: bool = Field(False, description="Enable shadow retrieval comparison alongside legacy retrieval")
    GRAPH_CANARY_PROVIDER_IDS: List[int] = Field(default_factory=list, description="Provider IDs eligible for live Graphiti canary retrieval")
    GRAPH_CANARY_TENANT_IDS: List[int] = Field(default_factory=list, description="Tenant IDs eligible for live Graphiti canary retrieval")

    # Knowledge Bounded Retrieval & Cache Settings (Specs 48, 49)
    KNOWLEDGE_FACTS_LIMIT: int = Field(5, description="Maximum factual knowledge items in bounded context (Spec 48)")
    KNOWLEDGE_BEHAVIOUR_LIMIT: int = Field(3, description="Maximum behavioural guidance items in bounded context (Spec 48)")
    KNOWLEDGE_EXAMPLES_LIMIT: int = Field(2, description="Maximum style examples in bounded context (Spec 48)")
    KNOWLEDGE_CACHE_TTL_SECONDS: int = Field(300, description="Redis knowledge retrieval cache TTL seconds (Spec 49)")

    # Curator Worker Settings
    CURATOR_WORKER_ENABLED: bool = Field(True, description="Enable background curator worker")
    CURATOR_WORKER_INTERVAL_SECONDS: float = Field(5.0, description="Curator worker polling interval in seconds")

    # Projection Worker Settings
    PROJECTION_WORKER_ENABLED: bool = Field(True, description="Enable background graph projection worker")
    PROJECTION_WORKER_INTERVAL_SECONDS: float = Field(5.0, description="Graph projection worker polling interval in seconds")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.OUTBOX_SHUTDOWN_GRACE_SECONDS >= self.OUTBOX_LEASE_SECONDS:
            raise ValueError("OUTBOX_SHUTDOWN_GRACE_SECONDS must be shorter than OUTBOX_LEASE_SECONDS")
        if self.APP_ENV in ("production", "prod"):
            if self.SECRET_KEY == "changeme":
                raise ValueError("SECRET_KEY must not be 'changeme' in production environment")
            if self.PUBLIC_API_KEY == "local-public-key-change-me":
                raise ValueError("PUBLIC_API_KEY must not be 'local-public-key-change-me' in production environment")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite database is not allowed in production environment")
            if self.GRAPH_KNOWLEDGE_ENABLED and self.NEO4J_PASSWORD == "bookings_dev_neo4j_password":
                raise ValueError("NEO4J_PASSWORD must not be 'bookings_dev_neo4j_password' in production environment when GRAPH_KNOWLEDGE_ENABLED is True")
        return self

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
