from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llama_base_url: str = "http://localhost:8080/v1"
    llama_model: str = "gemma-4-e4b-it"
    database_url: str = "postgresql+asyncpg://gemma:gemma@localhost:5432/gemma"
    workspace_dir: Path = PROJECT_ROOT / "workspace"

    obsidian_api_key: str = ""
    obsidian_host: str = "127.0.0.1"
    obsidian_port: int = 27124

    @field_validator("workspace_dir")
    @classmethod
    def _resolve_workspace(cls, v: Path) -> Path:
        return v if v.is_absolute() else (PROJECT_ROOT / v).resolve()


settings = Settings()
