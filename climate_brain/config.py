"""Configuration management for ClimateBrain."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # SwitchBot
    switchbot_token: str = ""
    switchbot_secret: str = ""

    # Weather
    openweather_api_key: str = ""
    openweather_lat: float = -6.2088
    openweather_lon: float = 106.8456

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Scheduler
    scheduler_enabled: bool = True
    control_interval_minutes: int = 5

    # Learning
    min_feedback_points: int = 20
    thermal_retrain_hours: int = 6
    comfort_retrain_hours: int = 12

    # Optimization
    optimization_strategy: str = "minimax"  # minimax, utilitarian, weighted
    temp_search_range: int = 4

    # Database
    db_path: str = "climate_brain.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
