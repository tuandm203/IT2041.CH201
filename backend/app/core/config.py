"""
Cấu hình ứng dụng.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DEFAULT_SAMPLE_TKB_PATH = (
    Path(__file__).resolve().parents[3]
    / "TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx"
)


class Settings(BaseSettings):
    """Cấu hình toàn cục."""
    app_name: str = "Schedule Optimizer"
    app_version: str = "0.1.0"
    upload_dir: Path = Path("/app/uploads")
    data_dir: Path = DEFAULT_DATA_DIR
    sample_tkb_path: Path = DEFAULT_SAMPLE_TKB_PATH
    max_file_size: int = 10 * 1024 * 1024  # 10 MB

    model_config = {"env_file": ".env"}


settings = Settings()
