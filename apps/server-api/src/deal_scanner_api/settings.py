import re
from functools import lru_cache
from ipaddress import ip_address
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEAL_SCANNER_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./.data/deal-scanner.db"
    supabase_db_url: str = ""
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
    ebay_sandbox_client_id: str = ""
    ebay_sandbox_client_secret: str = ""
    ebay_production_client_id: str = ""
    ebay_production_client_secret: str = ""
    ebay_deletion_endpoint_url: str = ""
    ebay_deletion_verification_token: str = ""
    ebay_notification_public_key_cache_seconds: int = Field(default=3600, ge=60, le=86_400)
    image_storage_dir: str = ".data/images"
    rate_limit_per_minute: int = Field(default=240, ge=10, le=10_000)
    sensitive_rate_limit_per_minute: int = Field(default=60, ge=5, le=1_000)

    @property
    def allowed_origins(self) -> list[str]:
        values = [*self.cors_origins.split(","), *self.extension_origins.split(",")]
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def validate_security_mode(self) -> "Settings":
        if (
            self.environment == "production"
            and self.supabase_db_url
            and self.database_url == "sqlite+aiosqlite:///./.data/deal-scanner.db"
        ):
            self.database_url = self.supabase_db_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        environment_credentials = (
            (self.ebay_production_client_id, self.ebay_production_client_secret)
            if self.ebay_environment == "production"
            else (self.ebay_sandbox_client_id, self.ebay_sandbox_client_secret)
        )
        if any(environment_credentials):
            self.ebay_client_id, self.ebay_client_secret = environment_credentials
        if self.environment == "production" and self.auth_mode == "development":
            raise ValueError("development auth is forbidden in production")
        if self.auth_mode == "supabase" and not self.supabase_url:
            raise ValueError("SUPABASE_URL is required for Supabase auth")
        if self.ebay_deletion_verification_token and not re.fullmatch(
            r"[A-Za-z0-9_-]{32,80}",
            self.ebay_deletion_verification_token,
        ):
            raise ValueError(
                "EBAY_DELETION_VERIFICATION_TOKEN must contain 32-80 letters, digits, underscores, or hyphens"
            )
        if self.ebay_deletion_endpoint_url:
            endpoint = urlparse(self.ebay_deletion_endpoint_url)
            if (
                endpoint.scheme != "https"
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.port not in (None, 443)
            ):
                raise ValueError("EBAY_DELETION_ENDPOINT_URL must be a public HTTPS URL on port 443")
            hostname = endpoint.hostname.casefold().rstrip(".")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise ValueError("EBAY_DELETION_ENDPOINT_URL must not use localhost")
            try:
                endpoint_ip = ip_address(hostname)
            except ValueError:
                endpoint_ip = None
            if endpoint_ip is not None and not endpoint_ip.is_global:
                raise ValueError("EBAY_DELETION_ENDPOINT_URL must not use a non-public IP address")
            if not self.ebay_deletion_verification_token:
                raise ValueError(
                    "EBAY_DELETION_VERIFICATION_TOKEN is required when EBAY_DELETION_ENDPOINT_URL is configured"
                )
        if self.ebay_environment == "production" and (self.ebay_client_id or self.ebay_client_secret):
            if not (
                self.ebay_client_id
                and self.ebay_client_secret
                and self.ebay_deletion_endpoint_url
                and self.ebay_deletion_verification_token
            ):
                raise ValueError(
                    "production eBay credentials, deletion endpoint URL, and verification token "
                    "must be configured together"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
