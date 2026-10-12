from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..core.config import Config
from .orm_models import Base, UNSPSC_EMBEDDING_DIMENSIONS


class Database:
    def __init__(self, db_config=None):
        self.db_config = db_config or Config.get_db_config()
        self.connection_string = (
            f"postgresql://{self.db_config.user}:{self.db_config.password}"
            f"@{self.db_config.host}:{self.db_config.port}/{self.db_config.dbname}"
            f"?sslmode={self.db_config.sslmode}"
        )
        self.engine = create_engine(
            self.connection_string,
            pool_pre_ping=True,
            pool_recycle=self.db_config.pool_recycle_seconds,
            pool_reset_on_return="rollback",
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def init_db(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.commit()

        if self.db_config.schema_sync:
            Base.metadata.create_all(bind=self.engine)
            self._ensure_schema_evolution()
            self._ensure_constraints()
            self._ensure_indexes()

    def _ensure_schema_evolution(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS previous_names text[]"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS previous_names_normalized text[]"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS company_status text"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS company_category text"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS country_of_origin text"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS incorporation_date date"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE lip_v2_company_enrichment "
                    "ADD COLUMN IF NOT EXISTS dissolution_date date"
                )
            )
            conn.commit()

    def _ensure_constraints(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    """
                    ALTER TABLE lip_v2_non_unspsc_rules
                    DROP CONSTRAINT IF EXISTS chk_lip_v2_non_unspsc_fallback_code_format
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE lip_v2_non_unspsc_rules
                    ADD CONSTRAINT chk_lip_v2_non_unspsc_fallback_code_format
                    CHECK (
                        fallback_unspsc_code IS NULL
                        OR fallback_unspsc_code ~ '^-?[0-9]{4,8}$'
                    )
                    """
                )
            )
            conn.commit()

    def _ensure_indexes(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lip_v2_line_item_solution_solved_for "
                    "ON lip_v2_line_item_solution USING gin (solved_for)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lip_v2_non_unspsc_rules_active_order "
                    "ON lip_v2_non_unspsc_rules (active, rule_order)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_search_document_trgm "
                    "ON lip_v2_unspsc_embeddings_v2 USING gin (search_document gin_trgm_ops)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lip_v2_company_enrichment_name_trgm "
                    "ON lip_v2_company_enrichment USING gin (company_name_normalized gin_trgm_ops)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_lip_v2_company_enrichment_previous_names_normalized "
                    "ON lip_v2_company_enrichment USING gin (previous_names_normalized)"
                )
            )
            if UNSPSC_EMBEDDING_DIMENSIONS <= 2000:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_hnsw "
                        "ON lip_v2_unspsc_embeddings_v2 USING hnsw (embedding vector_cosine_ops)"
                    )
                )
            conn.commit()

    def get_session(self):
        return self.SessionLocal()

    def close(self) -> None:
        self.engine.dispose()
