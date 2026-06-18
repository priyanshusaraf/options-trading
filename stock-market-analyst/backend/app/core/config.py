from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]  # backend/app/core → backend/app → backend → project root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    alpha_vantage_key: str = ""
    finnhub_key: str = ""
    fmp_key: str = ""
    fred_key: str = ""

    # Zerodha
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    cache_ttl_seconds: int = 3600
    benchmark_symbol: str = "^NSEI"

    # Paths
    data_dir: Path = ROOT_DIR / "data"
    parquet_dir: Path = ROOT_DIR / "data/parquet"
    sqlite_path: Path = ROOT_DIR / "data/sqlite/market.db"
    reports_dir: Path = ROOT_DIR / "data/reports"
    cache_dir: Path = ROOT_DIR / "data/cache"

    # Finance
    default_currency: str = "INR"
    risk_free_rate: float = 0.065

    def ensure_dirs(self) -> None:
        for d in [self.data_dir, self.parquet_dir, self.reports_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
