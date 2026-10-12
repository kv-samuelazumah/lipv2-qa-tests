from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test envs
    def load_dotenv() -> None:
        return None


load_dotenv()


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DatabaseConfig:
    dbname: str
    user: str
    password: str
    host: str
    port: int
    sslmode: str
    schema_sync: bool
    seed_non_unspsc_rules: bool
    pool_recycle_seconds: int
    seed_stable_lookups: bool = False
    seed_unstable_lookups: bool = False


class Config:
    @staticmethod
    def get_db_config() -> DatabaseConfig:
        dbname = os.getenv("POSTGRES_DB", "unspsc")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        sslmode = "require" if _truthy(os.getenv("POSTGRES_SSL"), default=False) else "prefer"
        schema_sync = _truthy(os.getenv("DB_SCHEMA_SYNC"), default=True)
        seed_non_unspsc_rules = _truthy(os.getenv("SEED_NON_UNSPSC_RULES"), default=False)
        pool_recycle_seconds = int(os.getenv("POSTGRES_POOL_RECYCLE_SECONDS", "1800"))

        return DatabaseConfig(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
            sslmode=sslmode,
            schema_sync=schema_sync,
            seed_non_unspsc_rules=seed_non_unspsc_rules,
            pool_recycle_seconds=pool_recycle_seconds,
            seed_stable_lookups=_truthy(os.getenv("SEED_STABLE_LOOKUPS"), default=False),
            seed_unstable_lookups=_truthy(os.getenv("SEED_UNSTABLE_LOOKUPS"), default=False),
        )

    @staticmethod
    def get_identify_search_model() -> str:
        return os.getenv("IDENTIFY_SEARCH_MODEL", "deepseek-chat")

    @staticmethod
    def get_identify_search_api_key() -> str | None:
        return os.getenv("DEEPSEEK_API_KEY")

    @staticmethod
    def get_identify_search_base_url() -> str:
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @staticmethod
    def get_web_reidentify_model() -> str:
        return os.getenv("WEB_REIDENTIFY_MODEL", Config.get_identify_search_model())

    @staticmethod
    def get_web_reidentify_api_key() -> str | None:
        return os.getenv("WEB_REIDENTIFY_API_KEY", Config.get_identify_search_api_key())

    @staticmethod
    def get_web_reidentify_base_url() -> str:
        return os.getenv("WEB_REIDENTIFY_BASE_URL", Config.get_identify_search_base_url())

    @staticmethod
    def get_evaluate_candidates_model() -> str:
        return os.getenv("EVALUATE_CANDIDATES_MODEL", Config.get_identify_search_model())

    @staticmethod
    def get_evaluate_candidates_api_key() -> str | None:
        return os.getenv("EVALUATE_CANDIDATES_API_KEY", Config.get_identify_search_api_key())

    @staticmethod
    def get_evaluate_candidates_base_url() -> str:
        return os.getenv("EVALUATE_CANDIDATES_BASE_URL", Config.get_identify_search_base_url())

    @staticmethod
    def get_unspsc_version() -> str:
        return os.getenv("UNSPSC_VERSION", "unknown")

    @staticmethod
    def get_openai_embedding_api_key() -> str | None:
        return os.getenv("OPENAI_API_KEY")

    @staticmethod
    def get_openai_embedding_model() -> str:
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    @staticmethod
    def get_openai_embedding_base_url() -> str | None:
        return os.getenv("OPENAI_BASE_URL")

    @staticmethod
    def get_elasticsearch_base_url() -> str:
        return os.getenv("ELASTICSEARCH_BASE_URL", "http://localhost:9200")

    @staticmethod
    def get_elasticsearch_index_name() -> str:
        return os.getenv("ELASTICSEARCH_UNSPSC_INDEX", "lip-v2-unspsc")

    @staticmethod
    def get_elasticsearch_api_key() -> str | None:
        return os.getenv("ELASTICSEARCH_API_KEY")

    @staticmethod
    def get_elasticsearch_username() -> str | None:
        return os.getenv("ELASTICSEARCH_USERNAME")

    @staticmethod
    def get_elasticsearch_password() -> str | None:
        return os.getenv("ELASTICSEARCH_PASSWORD")

    @staticmethod
    def get_unspsc_import_batch_size() -> int:
        return int(os.getenv("UNSPSC_IMPORT_BATCH_SIZE", "100"))

    @staticmethod
    def get_serper_api_key() -> str | None:
        return os.getenv("SERPER_API_KEY")

    @staticmethod
    def get_serper_base_url() -> str:
        return os.getenv("SERPER_BASE_URL", "https://google.serper.dev/search")

    @staticmethod
    def get_supplier_match_min_similarity() -> float:
        return float(os.getenv("SUPPLIER_MATCH_MIN_SIMILARITY", "0.75"))
