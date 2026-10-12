from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .models import PreAgenticRequest
from .loop import PreAgenticLoop
from ..persistence.repository import (
    PostgresLineItemSolutionRepository,
    PostgresNonUnspscRuleRepository,
)

if TYPE_CHECKING:
    from ..persistence.database import Database


class PreAgenticService:
    def __init__(self, db: Optional["Database"] = None):
        if db is None:
            from ..persistence.database import Database

            db = Database()
        self.db = db

    def initialize(self) -> None:
        self.db.init_db()

    def resolve(self, org_id: str, supplier_raw: str, line_item_raw: str) -> Optional[dict]:
        session = self.db.get_session()
        try:
            loop = PreAgenticLoop(
                solution_repo=PostgresLineItemSolutionRepository(session),
                rule_repo=PostgresNonUnspscRuleRepository(session),
            )
            result = loop.run(
                PreAgenticRequest(
                    org_id=org_id,
                    supplier_raw=supplier_raw,
                    line_item_raw=line_item_raw,
                )
            )
            return None if result is None else loop.serialize(result)
        finally:
            session.close()

    def close(self) -> None:
        self.db.close()
