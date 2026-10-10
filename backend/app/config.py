from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Meridian"
    app_version: str = "0.1.0"
    app_secret_key: str
    platform_database_url: str = "postgresql+psycopg://platform:platform@localhost:5432/platform"
    commerce_admin_url: str = "postgresql+psycopg://commerce_admin:commerce_admin@localhost:5432/commerce"
    mongo_admin_url: str = "mongodb://root:root@localhost:27017/?authSource=admin"
    demo_pg_host: str = "localhost"
    demo_pg_port: int = 5432
    demo_pg_database: str = "commerce"
    demo_pg_username: str = "commerce_reader"
    demo_pg_password: str = "commerce_reader"
    demo_mongo_host: str = "localhost"
    demo_mongo_port: int = 27017
    demo_mongo_database: str = "crm"
    demo_mongo_username: str = "crm_reader"
    demo_mongo_password: str = "crm_reader"
    demo_mongo_auth_source: str = "crm"
    mongo_writer_username: str = "crm_writer"
    mongo_writer_password: str = "crm_writer"
    import_pg_database: str = "imports"
    import_pg_username: str = "import_reader"
    import_pg_password: str = "import_reader"
    import_pg_writer_username: str = "import_writer"
    import_pg_writer_password: str = "import_writer"
    import_mongo_database: str = "imports"
    import_mongo_username: str = "import_reader"
    import_mongo_password: str = "import_reader"
    import_mongo_auth_source: str = "imports"
    import_mongo_writer_username: str = "import_writer"
    import_mongo_writer_password: str = "import_writer"
    seed_demo_data: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    upload_dir: str = ""
    max_upload_bytes: int = 8 * 1024 * 1024
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir) if self.upload_dir else Path(__file__).resolve().parents[1] / "data" / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def seed_data_path(self) -> Path:
        return Path(__file__).resolve().parent / "seed_data"

    @property
    def embedding_cache_path(self) -> Path:
        path = Path(__file__).resolve().parents[1] / ".cache" / "fastembed"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    try:
        Fernet(settings.app_secret_key.encode())
    except Exception as exc:
        raise RuntimeError("APP_SECRET_KEY must be a valid Fernet key.") from exc
    return settings
