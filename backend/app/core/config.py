"""
Cấu hình ứng dụng.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Cấu hình toàn cục."""
    app_name: str = "Schedule Optimizer"
    app_version: str = "0.1.0"
    upload_dir: Path = Path("/app/uploads")
    max_file_size: int = 10 * 1024 * 1024  # 10 MB

    model_config = {"env_file": ".env"}


settings = Settings()
