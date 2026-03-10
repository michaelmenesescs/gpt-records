from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str

    # Artist profile
    artist_name: str = "Artist"
    artist_genre: str = "Electronic"
    artist_location: str = "London, UK"
    artist_bio: str = "Electronic music producer and DJ"

    # Database
    database_url: str = "postgresql://gpt:gpt_secret@localhost:5432/gpt_records"

    # Qdrant vector store
    qdrant_url: str = "http://localhost:6333"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
