from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "GenSmile Server"
    version: str = "0.1.0"
    environment: str = "development"
    
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/gensmile",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    allowed_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://www.gensmile.ai",
            "https://gensmile.ai",
            "*",
        ],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "allowed_origins"),
    )
    create_tables_on_startup: bool = Field(default=True)
    jwt_algorithm: str = "HS256"
    access_token_secret: str = Field(
        default="change-this-access-secret-in-production",
        validation_alias=AliasChoices("ACCESS_TOKEN_SECRET", "access_token_secret"),
    )
    refresh_token_secret: str = Field(
        default="change-this-refresh-secret-in-production",
        validation_alias=AliasChoices("REFRESH_TOKEN_SECRET", "refresh_token_secret"),
    )
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "access_token_expire_minutes",
        ),
    )
    refresh_token_expire_days: int = Field(
        default=14,
        validation_alias=AliasChoices(
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "refresh_token_expire_days",
        ),
    )
    jwt_issuer: str = Field(
        default="gensmile-server",
        validation_alias=AliasChoices("JWT_ISSUER", "jwt_issuer"),
    )
    frontend_base_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_BASE_URL", "frontend_base_url"),
    )
    password_reset_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
            "password_reset_token_expire_minutes",
        ),
    )
    invitation_token_expire_hours: int = Field(
        default=72,
        validation_alias=AliasChoices(
            "INVITATION_TOKEN_EXPIRE_HOURS",
            "invitation_token_expire_hours",
        ),
    )
    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST", "smtp_host"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "smtp_port"),
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_USE_TLS", "smtp_use_tls"),
    )
    smtp_use_ssl: bool = Field(
        default=False,
        validation_alias=AliasChoices("SMTP_USE_SSL", "smtp_use_ssl"),
    )
    smtp_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME", "smtp_username"),
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "smtp_password"),
    )
    smtp_from_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "smtp_from_email"),
    )
    smtp_from_name: str = Field(
        default="GenSmile",
        validation_alias=AliasChoices("SMTP_FROM_NAME", "smtp_from_name"),
    )
    uploads_directory: str = Field(
        default=str(Path("uploads")),
        validation_alias=AliasChoices("UPLOADS_DIRECTORY", "uploads_directory"),
    )

    # 90-day onboarding drip campaign
    drip_campaign_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DRIP_CAMPAIGN_ENABLED", "drip_campaign_enabled"),
    )
    drip_campaign_send_hour_utc: int = Field(
        default=13,
        validation_alias=AliasChoices("DRIP_CAMPAIGN_SEND_HOUR_UTC", "drip_campaign_send_hour_utc"),
    )

    # Subscription renewal reminder (fires once per billing period, N days
    # before Subscription.current_period_end)
    renewal_reminder_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RENEWAL_REMINDER_ENABLED", "renewal_reminder_enabled"),
    )
    renewal_reminder_days_before: int = Field(
        default=3,
        validation_alias=AliasChoices("RENEWAL_REMINDER_DAYS_BEFORE", "renewal_reminder_days_before"),
    )
    renewal_reminder_send_hour_utc: int = Field(
        default=13,
        validation_alias=AliasChoices("RENEWAL_REMINDER_SEND_HOUR_UTC", "renewal_reminder_send_hour_utc"),
    )

    # Self-service cancellation refunds: a user cancelling immediately can
    # request a refund of their most recent payment, but only within this
    # many days of that payment -- otherwise support/admin has to handle it
    # manually via the admin panel (no window limit there).
    self_service_refund_window_days: int = Field(
        default=14,
        validation_alias=AliasChoices("SELF_SERVICE_REFUND_WINDOW_DAYS", "self_service_refund_window_days"),
    )

    # S3 / object storage
    s3_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("S3_ENABLED", "s3_enabled"),
    )
    s3_bucket_name: str = Field(
        default="",
        validation_alias=AliasChoices("S3_BUCKET_NAME", "s3_bucket_name"),
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "s3_region"),
    )
    aws_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "aws_access_key_id"),
    )
    aws_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"),
    )    
    s3_folder: str = Field( 
        default="simulations",
        validation_alias=AliasChoices("S3_FOLDER", "s3_folder"),
    )

    # Rate limiting
    rate_limit_login: str = Field(
        default="10/minute",
        validation_alias=AliasChoices("RATE_LIMIT_LOGIN", "rate_limit_login"),
    )
    rate_limit_forgot_password: str = Field(
        default="5/minute",
        validation_alias=AliasChoices("RATE_LIMIT_FORGOT_PASSWORD", "rate_limit_forgot_password"),
    )
    rate_limit_embed_generate: str = Field(
        default="10/hour",
        validation_alias=AliasChoices("RATE_LIMIT_EMBED_GENERATE", "rate_limit_embed_generate"),
    )
    rate_limit_ai_process: str = Field(
        default="20/minute",
        validation_alias=AliasChoices("RATE_LIMIT_AI_PROCESS", "rate_limit_ai_process"),
    )
    # Applied to every route that doesn't have its own more specific limit
    # above (requires slowapi's SlowAPIMiddleware to be registered -- see
    # main.py). Generous on purpose: a clinic's staff can share one public
    # IP behind office wifi/NAT, and the app polls (video/simulation status)
    # every 2-3s per active user -- this is an anti-flood/anti-bot ceiling,
    # not meant to constrain normal multi-user clinic traffic.
    rate_limit_default: str = Field(
        default="300/minute",
        validation_alias=AliasChoices("RATE_LIMIT_DEFAULT", "rate_limit_default"),
    )

    # IP blocklist (see app.core.ip_blocklist) -- how many rate-limit
    # violations / failed logins within the window before an IP gets
    # outright blocked, and for how long.
    ip_block_strike_threshold: int = Field(
        default=8,
        validation_alias=AliasChoices("IP_BLOCK_STRIKE_THRESHOLD", "ip_block_strike_threshold"),
    )
    ip_block_strike_window_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("IP_BLOCK_STRIKE_WINDOW_SECONDS", "ip_block_strike_window_seconds"),
    )
    ip_block_duration_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("IP_BLOCK_DURATION_SECONDS", "ip_block_duration_seconds"),
    )

    # Email verification
    email_verification_token_expire_hours: int = Field(
        default=24,
        validation_alias=AliasChoices(
            "EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS",
            "email_verification_token_expire_hours",
        ),
    )

    stripe_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "stripe_secret_key"),
    )
    stripe_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PUBLISHABLE_KEY", "stripe_publishable_key"),
    )
    stripe_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_WEBHOOK_SECRET", "stripe_webhook_secret"),
    )

    appstore_bundle_id: str = Field(default="com.gensmile.app", validation_alias=AliasChoices("APPSTORE_BUNDLE_ID", "appstore_bundle_id"))
    appstore_app_apple_id: int = Field(default=0, validation_alias=AliasChoices("APPSTORE_APP_APPLE_ID", "appstore_app_apple_id"))

    # App Store Connect API (Finance role) -- for fetching real sales/proceeds data.
    # These three are identifiers, not secrets (the .p8 file is the actual secret).
    appstore_connect_issuer_id: str = Field(default="", validation_alias=AliasChoices("APPSTORE_CONNECT_ISSUER_ID", "appstore_connect_issuer_id"))
    appstore_connect_key_id: str = Field(default="", validation_alias=AliasChoices("APPSTORE_CONNECT_KEY_ID", "appstore_connect_key_id"))
    appstore_connect_vendor_number: str = Field(default="", validation_alias=AliasChoices("APPSTORE_CONNECT_VENDOR_NUMBER", "appstore_connect_vendor_number"))
    appstore_connect_private_key_path: str = Field(
        default="certs/AuthKey_9TBTZ23N29.p8",
        validation_alias=AliasChoices("APPSTORE_CONNECT_PRIVATE_KEY_PATH", "appstore_connect_private_key_path"),
    )

    # Subscription price IDs — tiered by duration
    stripe_price_id_starter: str = Field(
        default="price_1TgjjkLlby0MmRmrfJshB8kf",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_STARTER", "stripe_price_id_starter"),
    )
    stripe_price_id_professional: str = Field(
        default="price_1TgjjxLlby0MmRmrLMEYE4eN",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_PROFESSIONAL", "stripe_price_id_professional"),
    )
    stripe_price_id_credits: str = Field(
        default="price_1TgkDpLlby0MmRmrbEL8ihCj",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_CREDITS", "stripe_price_id_credits"),
    )
    stripe_price_id_clinic: str = Field(
        default="price_1TlX3SLlby0MmRmrQmdMIPN2",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_CLINICS", "stripe_price_id_clinic"),
    )
    stripe_price_id_staff: str = Field(
        default="price_1TlX3CLlby0MmRmreMtX2anS",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_STAFFS", "stripe_price_id_staff"),
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    fal_key: str = Field(
        default="",
        validation_alias=AliasChoices("FAL_KEY", "fal_key"),
    )
    runpod_api: str = Field(
        default="",
        validation_alias=AliasChoices("RUNPOD_API", "runpod_api"),
    )
    endpoint_id: str = Field(
        default="",
        validation_alias=AliasChoices("ENDPOINT_ID", "endpoint_id"),
    )
    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "google_api_key"),
    )
    elevenlabs_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ELEVENLABS_API_KEY", "elevenlabs_api_key"),
    )
    elevenlabs_voice_id: str = Field(
        default="",
        validation_alias=AliasChoices("ELEVENLABS_VOICE_ID", "elevenlabs_voice_id"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    iap_env: str = Field(
        default="",
        validation_alias=AliasChoices("IAP_ENV", "iap_env"),
    )
    app_env: str = Field(
        default="",
        validation_alias=AliasChoices("APP_ENV", "app_env"),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_database_driver(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        if not value.startswith("postgresql+asyncpg://"):
            return value

        parts = urlsplit(value)
        query_params = parse_qsl(parts.query, keep_blank_values=True)
        normalized_query_params: list[tuple[str, str]] = []

        for key, query_value in query_params:
            if key == "sslmode":
                normalized_query_params.append(("ssl", query_value))
                continue

            if key == "channel_binding":
                continue

            normalized_query_params.append((key, query_value))

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(normalized_query_params, doseq=True),
                parts.fragment,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
