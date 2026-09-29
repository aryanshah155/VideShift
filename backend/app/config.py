"""Application configuration loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

try:  # pragma: no cover - trivial
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


class Settings(BaseSettings):
    """Runtime settings for the VibeShift API."""

    model_config = SettingsConfigDict(env_prefix="VIBESHIFT_", extra="ignore")

    port: int = 8000
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "vibeshift"
    data_dir: Path = BASE_DIR / "data"

    # Cors origins allowed for the dev frontend
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def csv_path(self) -> Path:
        """Expected location of the Spotify tracks CSV."""
        return self.data_dir / "tracks_features.csv"


@lru_cache
def get_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv(BASE_DIR / ".env")
    return Settings()
