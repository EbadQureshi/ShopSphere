from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    hf_token: str = ""
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    groq_api_key: str = ""
    groq_chat_model: str = "qwen/qwen3.8-27b"
    chroma_path: str = "./chroma_db"
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    @property
    def origins(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def resolved_chroma_path(self) -> Path:
        path = Path(self.chroma_path)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path

settings = Settings()
