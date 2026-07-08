"""Application configuration settings.

This module defines the :class:`Settings` class which centralizes
configuration for the FastAPI Bookings project. Settings are loaded
from environment variables where available and fall back to sensible
defaults otherwise. See the documentation for details on how these
values are used throughout the application.
"""

# BaseSettings moved to pydantic_settings in Pydantic v2
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for environments with Pydantic v1
    from pydantic import BaseSettings
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

    # ClickSend SMS/MMS Settings
    CLICKSEND_API_USERNAME: str = Field("", description="ClickSend API username")
    CLICKSEND_API_KEY: str = Field("", description="ClickSend API key")

    # Stripe Settings
    STRIPE_PUBLISHABLE_KEY: str = Field("", description="Stripe Publishable Key")
    STRIPE_SECRET_KEY: str = Field("", description="Stripe Secret Key")
    STRIPE_WEBHOOK_SECRET: str = Field("", description="Stripe Webhook Secret")

    # Firebase Settings
    FIREBASE_CREDENTIALS_JSON: str = Field("", description="Firebase Service Account JSON string or filepath")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.SECRET_KEY == "changeme":
                raise ValueError("SECRET_KEY must not be 'changeme' in production environment")
            if self.PUBLIC_API_KEY == "local-public-key-change-me":
                raise ValueError("PUBLIC_API_KEY must not be 'local-public-key-change-me' in production environment")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite database is not allowed in production environment")
        return self

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()