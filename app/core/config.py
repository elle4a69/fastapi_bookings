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

    # Security
    SECRET_KEY: str = Field(
        "changeme",
        description="Secret key used to sign JWT tokens",
    )
    ENCRYPTION_KEY: str = Field(
        "",
        description="Dedicated cryptographic key for database envelope encryption (SEC-001)",
    )
    JWT_ISSUER: str = Field(
        "fastapi-bookings",
        description="Expected JWT issuer claim (iss) (AUTH-004)",
    )
    JWT_AUDIENCE: str = Field(
        "fastapi-bookings-api",
        description="Expected JWT audience claim (aud) (AUTH-004)",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60,
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

    # Outbox settings
    OUTBOX_POLL_INTERVAL: float = Field(5.0, description="Outbox worker polling interval in seconds")
    OUTBOX_MAX_RETRIES: int = Field(5, description="Max retries for enqueued outbox events")

    # OpenTelemetry / observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        "http://localhost:4318", description="OTLP exporter base endpoint URL"
    )
    OTEL_SDK_DISABLED: bool = Field(
        False, description="Set to True to disable OTel SDK"
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.APP_ENV == "production":
            insecure_keys = {
                "changeme",
                "test-secret-key",
                "local-secret-key",
                "fallback-default-secret-key-change-me",
                "local-public-key-change-me",
            }
            if not self.SECRET_KEY or self.SECRET_KEY in insecure_keys:
                raise ValueError("SECRET_KEY must not be empty or an insecure default in production environment")
            if not self.ENCRYPTION_KEY or self.ENCRYPTION_KEY in insecure_keys:
                raise ValueError("ENCRYPTION_KEY must be configured with a dedicated secure key in production environment")
            if self.PUBLIC_API_KEY == "local-public-key-change-me":
                raise ValueError("PUBLIC_API_KEY must not be 'local-public-key-change-me' in production environment")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite database is not allowed in production environment")
        return self

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
