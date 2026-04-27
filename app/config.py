from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    route_decision_logging: bool = Field(default=True, alias="ROUTE_DECISION_LOGGING")

    firecrawl_api_key: str = Field(default="", alias="FIRECRAWL_API_KEY")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    searxng_base_url: str = Field(default="http://websearch-searxng:8080", alias="SEARXNG_BASE_URL")

    tavily_daily_soft_cap_calls: int = Field(default=8, alias="TAVILY_DAILY_SOFT_CAP_CALLS")
    tavily_monthly_cap_calls: int = Field(default=150, alias="TAVILY_MONTHLY_CAP_CALLS")
    tavily_reserve_percent_critical: int = Field(
        default=25, alias="TAVILY_RESERVE_PERCENT_CRITICAL"
    )

    request_timeout_seconds: float = 10.0
    default_max_results: int = 5


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BUDGET_DB_PATH = (
    Path("/data/tavily_budget.sqlite3")
    if Path("/data").exists()
    else ROOT_DIR / ".data" / "tavily_budget.sqlite3"
)
