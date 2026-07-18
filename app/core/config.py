from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "healeka-voice-agent"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8080
    public_base_url: str = "http://localhost:8080"
    public_ws_base_url: str = "ws://localhost:8080"
    shutdown_grace_seconds: int = 30

    admin_api_key: str = Field(default="change-me-admin-key")
    plivo_validate_signature: bool = True
    # Comma-separated origins for the admin dashboard (e.g. http://localhost:5173)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_answer_url: str = ""
    plivo_hangup_url: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice_name: str = "Aoede"
    gemini_vad_silence_ms: int = 900
    interrupt_grace_seconds: float = 3.0
    utterance_interrupt_grace_seconds: float = 0.45

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "voice_agent"

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    tenant_cache_ttl_seconds: int = 300
    department_cache_ttl_seconds: int = 600

    hms_origin_host_pattern: str = "https://{subdomain}.healeka.com"
    hms_http_timeout_seconds: float = 10.0
    hms_http_max_connections: int = 100

    plivo_audio_content_type: str = "audio/x-mulaw;rate=8000"
    plivo_sample_rate: int = 8000
    gemini_input_sample_rate: int = 16000
    gemini_output_sample_rate: int = 24000

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
