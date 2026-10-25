# app/config.py — Pydantic Settings (env-based config)
# Concept: env files separate config from code (12-factor app). Pydantic validates at startup.
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "InferenceHub"
    secret_key: str
    db_host: str = "localhost"
    db_port: int = 5432
    redis_url: str = "redis://localhost:6379/0"
