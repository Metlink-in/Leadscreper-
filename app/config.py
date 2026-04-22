from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    search_api_provider: str = "searchapi"
    search_api_key: Optional[str] = None
    serp_api_key: Optional[str] = None
    search_api_base_url: str = "https://www.searchapi.io/api/v1"
    gemini_api_key: str
    openai_api_key: Optional[str] = None
    app_secret: str
    max_results_per_source: int = 20
    enable_ai_enrichment: bool = True
    export_dir: str = "exports"
    cors_origins: List[str] = ["*"]


settings = Settings()
