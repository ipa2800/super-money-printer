"""Pydantic Settings — 读 .env + config/default.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # 数据库
    db_path: str = "./etf_data.db"

    # 服务器
    host: str = "0.0.0.0"
    port: int = 6000

    # 数据源凭证
    tushare_token: str = ""
    baostock_login_user: str = ""
    baostock_login_psw: str = ""

    # SSL
    ssl_verify: bool = True

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_path_resolved(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else PROJECT_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_yaml_config() -> dict[str, Any]:
    """读 config/default.yaml (合并配置, Phase 1.5 拆文件)。"""
    path = PROJECT_ROOT / "config" / "default.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}