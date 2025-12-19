import os
from datetime import timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class AppConfig(BaseModel):
    admin_group_id: int
    gym_group_id: int
    capacity: int
    reserve_window_minutes: int
    session_duration_minutes: int
    timezone: str
    database_path: str
    log_level: str = "DEBUG"
    super_users: list[int] = []
    bot_token: str

    @property
    def reserve_window(self) -> timedelta:
        return timedelta(minutes=self.reserve_window_minutes)

    @property
    def session_duration(self) -> timedelta:
        return timedelta(minutes=self.session_duration_minutes)


def load_settings(yaml_path: Path):
    data = {}
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in environment variables.")

    data["bot_token"] = BOT_TOKEN
    database_override = os.getenv("DATABASE_URL")
    if database_override:
        data["database_path"] = database_override
    return AppConfig(**data)


config_path = Path("/Users/dhruvramdev/Desktop/gim_gym_bot/config.yaml")
CONFIG = load_settings(config_path)
