from pathlib import Path

from pydantic import model_validator
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
    # Shown in the dashboard greeting; set USER_NAME in .env to change it
    user_name: str = "Malek"
    # readonly: the app can read emails but never send, delete or modify them
    gmail_scopes: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    # DEMO=true (env var or .env): fictional data in demo.db, your real emails are never touched
    demo: bool = False

    @model_validator(mode="after")
    def _use_demo_database(self) -> "Settings":
        if self.demo:
            self.db_path = BASE_DIR / "demo.db"
            self.user_name = "Alex"
        return self


settings = Settings()
