"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Database
    database_url: str

    # Ashby
    ashby_webhook_secret: str
    ashby_api_key: str

    # Slack
    slack_bot_token: str
    slack_signing_secret: str

    # Application
    log_level: str = "INFO"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"


settings = Settings.model_validate({})
