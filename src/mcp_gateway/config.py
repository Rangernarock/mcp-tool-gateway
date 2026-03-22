"""
Configuration management for MCP Tool Gateway.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from enum import Enum


class Network(str, Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ethereum"
    BASE = "base"
    BASE_SEPOLIA = "base-sepolia"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"


class Settings(BaseSettings):
    """Application settings."""
    
    # App settings
    app_name: str = "MCP Tool Gateway"
    version: str = "0.1.0"
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Network settings
    network: Network = Field(default=Network.BASE_SEPOLIA, env="NETWORK")
    rpc_url: str = Field(default="", env="RPC_URL")
    
    # Payment settings
    payment_token: str = Field(default="USDC", env="PAYMENT_TOKEN")
    payment_token_address: Optional[str] = Field(default=None, env="PAYMENT_TOKEN_ADDRESS")
    
    # Security settings
    api_key_header: str = "X-API-Key"
    require_api_key: bool = Field(default=True, env="REQUIRE_API_KEY")
    max_daily_spent: float = Field(default=1000.0, env="MAX_DAILY_SPENT")
    max_per_call: float = Field(default=100.0, env="MAX_PER_CALL")
    high_value_threshold: float = Field(default=100.0, env="HIGH_VALUE_THRESHOLD")
    
    # Escrow settings
    escrow_timeout_seconds: int = Field(default=300, env="ESCROW_TIMEOUT")
    dispute_window_seconds: int = Field(default=86400, env="DISPUTE_WINDOW")
    slash_percent: int = Field(default=10, env="SLASH_PERCENT")
    
    # Execution settings
    max_execution_time_ms: int = Field(default=30000, env="MAX_EXECUTION_TIME_MS")
    max_memory_mb: int = Field(default=512, env="MAX_MEMORY_MB")
    
    # Fraud detection
    fraud_detection_enabled: bool = Field(default=True, env="FRAUD_DETECTION_ENABLED")
    velocity_threshold_per_minute: int = Field(default=10, env="VELOCITY_THRESHOLD")
    anomaly_threshold: float = Field(default=0.8, env="ANOMALY_THRESHOLD")
    
    # CORS
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
