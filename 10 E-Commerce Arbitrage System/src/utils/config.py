"""Configuration management for the arbitrage system."""

import os
from pathlib import Path
from typing import Any, Dict
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AmazonConfig(BaseModel):
    """Amazon API configuration."""

    sp_api: Dict[str, str] = {}
    pa_api: Dict[str, str] = {}
    target_marketplace: str = "amazon.com"


class KeepaConfig(BaseModel):
    """Keepa API configuration."""

    api_key: str = ""
    rate_limit: int = 120


class ProfitConfig(BaseModel):
    """Profit calculation settings."""

    min_roi: float = 30.0
    amazon_fees: Dict[str, float] = Field(default_factory=dict)
    costs: Dict[str, float] = Field(default_factory=dict)
    target_profit_margin: float = 0.35


class FilterConfig(BaseModel):
    """Deal filtering criteria."""

    max_sales_rank: Dict[str, int] = Field(default_factory=dict)
    max_number_of_sellers: int = 10
    prefer_fba_sellers_under: int = 5
    min_source_price: float = 5.0
    max_source_price: float = 200.0
    min_amazon_price: float = 15.0
    min_review_count: int = 10
    min_average_rating: float = 3.5
    exclude_used: bool = True
    exclude_refurbished: bool = False
    excluded_categories: list = Field(default_factory=list)
    excluded_brands: list = Field(default_factory=list)


class NotificationConfig(BaseModel):
    """Notification settings."""

    email: Dict[str, Any] = Field(default_factory=dict)
    telegram: Dict[str, Any] = Field(default_factory=dict)
    sms: Dict[str, Any] = Field(default_factory=dict)


class Config(BaseSettings):
    """Main configuration class."""

    # General settings
    database_path: str = "data/deals.db"
    log_level: str = "INFO"
    log_path: str = "logs/arbitrage.log"

    # Nested configurations
    amazon: AmazonConfig = Field(default_factory=AmazonConfig)
    keepa: KeepaConfig = Field(default_factory=KeepaConfig)
    profit: ProfitConfig = Field(default_factory=ProfitConfig)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    # Scanning
    scanning: Dict[str, Any] = Field(default_factory=dict)

    # Scheduler
    scheduler: Dict[str, str] = Field(default_factory=dict)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    """Manages loading and accessing configuration."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration manager.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config_dict = self._load_yaml()
        self.config = self._create_config()

    def _load_yaml(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            # Try example config
            example_path = Path(str(self.config_path).replace(".yaml", ".example.yaml"))
            if example_path.exists():
                print(
                    f"Warning: {self.config_path} not found. Using {example_path}"
                )
                self.config_path = example_path
            else:
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}"
                )

        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def _create_config(self) -> Config:
        """Create Pydantic config from dictionary."""
        # Flatten nested structure for Pydantic
        config_data = {
            "database_path": self.config_dict.get("general", {}).get(
                "database_path", "data/deals.db"
            ),
            "log_level": self.config_dict.get("general", {}).get("log_level", "INFO"),
            "log_path": self.config_dict.get("general", {}).get(
                "log_path", "logs/arbitrage.log"
            ),
            "amazon": self.config_dict.get("amazon", {}),
            "keepa": self.config_dict.get("keepa", {}),
            "profit": self.config_dict.get("profit", {}),
            "filters": self.config_dict.get("filters", {}),
            "notifications": self.config_dict.get("notifications", {}),
            "scanning": self.config_dict.get("scanning", {}),
            "scheduler": self.config_dict.get("scheduler", {}),
        }

        return Config(**config_data)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'amazon.sp_api.client_id')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config_dict

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def get_amazon_credentials(self) -> Dict[str, str]:
        """Get Amazon API credentials."""
        return {
            "refresh_token": self.get("amazon.sp_api.refresh_token", ""),
            "client_id": self.get("amazon.sp_api.client_id", ""),
            "client_secret": self.get("amazon.sp_api.client_secret", ""),
            "marketplace_id": self.get("amazon.sp_api.marketplace_id", ""),
        }

    def get_keepa_key(self) -> str:
        """Get Keepa API key."""
        return self.get("keepa.api_key", "")

    def get_min_roi(self) -> float:
        """Get minimum ROI threshold."""
        return self.get("profit.min_roi", 30.0)

    def get_enabled_scanners(self) -> list:
        """Get list of enabled scanners."""
        return self.get("scanning.enabled_scanners", ["amazon"])

    def get_notification_config(self, channel: str) -> Dict[str, Any]:
        """Get notification configuration for a specific channel.

        Args:
            channel: Notification channel (email, telegram, sms)

        Returns:
            Channel configuration
        """
        return self.get(f"notifications.{channel}", {})

    @property
    def database_url(self) -> str:
        """Get SQLAlchemy database URL."""
        db_path = self.config.database_path
        if not db_path.startswith("sqlite:///"):
            db_path = f"sqlite:///{db_path}"
        return db_path


# Global config instance
_config_manager: ConfigManager = None


def get_config(config_path: str = "config/config.yaml") -> ConfigManager:
    """Get global configuration manager instance.

    Args:
        config_path: Path to configuration file

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager
