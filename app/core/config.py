from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder: this file is backend/app/core/config.py, so we go up 3 levels
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    client_secret_path: Path = BASE_DIR / "client_secret.json"
    token_path: Path = BASE_DIR / "token.json"
    db_path: Path = BASE_DIR / "jobtracker.db"
    # No news for this many days after your last step -> ghosted (or expired, if it was your turn)
    ghost_days: int = 15
    # readonly: the app can read emails but never send, delete or modify them
    gmail_scopes: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]


settings = Settings()
