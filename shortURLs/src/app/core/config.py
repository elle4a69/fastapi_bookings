from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


HMAC_MIN_SECRET_BYTES = {
    "HS256": 32,
    "HS384": 48,
    "HS512": 64,
}


class Settings(BaseSettings):
    database_url: str = "mongodb://db:27017"
    database_name: str = "url_shortener"
    database_collection_name: str = "urls"
    database_server_selection_timeout_ms: int = Field(default=3000, ge=100, le=30000)
    short_base_url: str = "http://short.url"
    short_url_retry_count: int = 5
    db_retry_count: int = 3
    db_retry_delay_seconds: float = 0.2
    enable_unique_indexes: bool = True
    index_strict_mode: bool = True
    max_batch_size: int = Field(default=100, ge=1, le=1000)
    batch_max_concurrency: int = Field(default=10, ge=1, le=100)
    max_request_body_bytes: int = Field(default=524288, ge=1024, le=10485760)

    secret_key: str = "replace_this_with_a_32_byte_minimum_secret_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    enable_rate_limit: bool = False
    enable_docs_url: bool
    enable_redoc_url: bool
    cors_allow_origins: str = ""
    cors_allow_credentials: bool = True
    service_name: str = "url-shortener"
    log_level: str = "INFO"
    log_json: bool = True
    enable_metrics: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def validate_hmac_secret_length(self):
        algorithm = (self.algorithm or "").upper()
        required_bytes = HMAC_MIN_SECRET_BYTES.get(algorithm)
        if (
            required_bytes is not None
            and len(self.secret_key.encode("utf-8")) < required_bytes
        ):
            raise ValueError(
                f"secret_key is too short for {algorithm}. "
                f"Expected at least {required_bytes} bytes."
            )
        return self

    @model_validator(mode="after")
    def validate_batch_concurrency(self):
        if self.batch_max_concurrency > self.max_batch_size:
            raise ValueError("batch_max_concurrency cannot exceed max_batch_size")
        return self

    def cors_allow_origins_list(self) -> list[str]:
        raw = (self.cors_allow_origins or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()
