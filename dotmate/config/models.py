from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import yaml
from pathlib import Path


class Schedule(BaseModel):
    cron: str
    type: str
    params: Optional[Dict[str, Any]] = None


class Device(BaseModel):
    name: str
    device_id: str
    schedules: Optional[List[Schedule]] = None


class Config(BaseModel):
    api_key: str
    devices: List[Device]


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    return Config(**data)