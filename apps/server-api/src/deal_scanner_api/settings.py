from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEAL_SCANNER_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./.data/deal-scanner.db"
    database_role: str = Field(default="authenticated", pattern=r"^[a-z_][a-z0-9_]*$")
    auto_create_db: bool = True
    auth_mode: str = "development"
    supabase_url: str | None = None
    supabase_service_role_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    cors_origins: str = "http://127.0.0.1:4200,http://localhost:4200,tauri://localhost,http://tauri.localhost"
    extension_origins: str = ""
    api_title: str = "Deal Scanner API"
    api_version: str = "0.1.0"
    default_lease_seconds: int = Field(default=300, ge=60, le=3600)
    development_user_id: str = "00000000-0000-4000-8000-000000000001"
    ntfy_url: str = ""
    ebay_environment: str = "sandbox"
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    image_storage_dir: str = ".data/images"
    rate_limit_per_minute: int = Field(default=240, ge=10, le=10_000)
    sensitive_rate_limit_per_minute: int = Field(default=60, ge=5, le=1_000)

    @property
    def allowed_origins(self) -> list[str]:
        values = [*self.cors_origins.split(","), *self.extension_origins.split(",")]
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def validate_security_mode(self) -> "Settings":
        if self.environment == "production" and self.auth_mode == "development":
            raise ValueError("development auth is forbidden in production")
        if self.auth_mode == "supabase" and not self.supabase_url:
            raise ValueError("SUPABASE_URL is required for Supabase auth")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
