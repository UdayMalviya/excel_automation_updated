from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = Field(default="browser-automation-platform", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    display: str = Field(default=":99", alias="DISPLAY")
    playwright_headless: bool = Field(default=False, alias="PLAYWRIGHT_HEADLESS")
    playwright_timeout_ms: int = Field(default=30000, alias="PLAYWRIGHT_TIMEOUT_MS")
    playwright_keep_open_ms: int = Field(default=10000, alias="PLAYWRIGHT_KEEP_OPEN_MS")
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    public_novnc_url: str = Field(
        default="http://localhost:6080/vnc.html?autoconnect=true&resize=remote",
        alias="PUBLIC_NOVNC_URL",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
