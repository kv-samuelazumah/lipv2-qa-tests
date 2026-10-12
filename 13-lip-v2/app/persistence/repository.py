from __future__ import annotations

import re
from typing import List, Optional, Protocol
from uuid import UUID

from ..pre_agentic.models import LineItemSolution, NonUnspscRule
from ..pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier

try:
    from sqlalchemy import desc, or_, text
    from sqlalchemy.orm import Session
    from .orm_models import (
        LipV2CompanyEnrichment,
        LipV2LineItemSolution,
        LipV2NonUnspscRule,
        LipV2SupplierCompanyMatch,
    )
    SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test envs
    desc = None
    or_ = None
    text = None
    Session = object
    LipV2CompanyEnrichment = None
    LipV2LineItemSolution = None
    LipV2NonUnspscRule = None
    LipV2SupplierCompanyMatch = None
    SQLALCHEMY_AVAILABLE = False


class LineItemSolutionRepository(Protocol):
    def find_unstable(self, lookup_hash: str, org_id: str) -> Optional[LineItemSolution]:
        ...

    def find_stable(self, lookup_hash: str) -> Optional[LineItemSolution]:
        ...

    def upsert_agentic_solution(
        self,
        *,
        org_id: str,
        supplier_raw: str,
        line_item_raw: str,
        unspsc_code: str,
        unspsc_level: str,
        reasoning: Optional[dict] = None,
        selected_label: Optional[str] = None,
    ) -> LineItemSolution:
        ...


class NonUnspscRuleRepository(Protocol):
    def find_first_match(self, line_item_text: str) -> Optional[NonUnspscRule]:
        ...


class CompanyEnrichmentRepository(Protocol):
    def find_by_companies_house_number(self, companies_house_number: str):
        ...

    def find_by_company_name_normalized(self, company_name_normalized: str):
        ...

    def find_best_fuzzy_match(self, company_name_normalized: str, min_similarity: float):
        ...

    def upsert_company(
        self,
        *,
        company_name_raw: str,
        company_name_normalized: str,
        companies_house_number: str,
        sic_codes: List[str],
        sic_labels: List[str],
        previous_names: List[str],
        previous_names_normalized: List[str],
        company_status: Optional[str],
        company_category: Optional[str],
        country_of_origin: Optional[str],
        incorporation_date,
        dissolution_date,
        vat_number: Optional[str],
        source_month: str,
        source_file_name: Optional[str],
    ):
        ...


class SupplierCompanyMatchRepository(Protocol):
    def find_by_supplier_normalized(self, supplier_normalized: str):
        ...

    def upsert_match(
        self,
        *,
        supplier_raw: str,
        supplier_normalized: str,
        companies_house_number: str,
        match_method: str,
        match_confidence: float,
    ):
        ...


class InMemoryLineItemSolutionRepository:
    def __init__(self, rows: Optional[List[LineItemSolution]] = None):
        self.rows = [row.recompute_stable() for row in (rows or [])]

    def find_unstable(self, lookup_hash: str, org_id: str) -> Optional[LineItemSolution]:
        for row in self.rows:
            if row.lookup_hash != lookup_hash:
                continue
            if row.stable:
                continue
            if org_id not in row.solved_for:
                continue
            return row
        return None

    def find_stable(self, lookup_hash: str) -> Optional[LineItemSolution]:
        for row in self.rows:
            if row.lookup_hash == lookup_hash and row.stable:
                return row
        return None

    def upsert_agentic_solution(
        self,
        *,
        org_id: str,
        supplier_raw: str,
        line_item_raw: str,
        unspsc_code: str,
        unspsc_level: str,
        reasoning: Optional[dict] = None,
        selected_label: Optional[str] = None,
    ) -> LineItemSolution:
        supplier_normalized = normalize_supplier(supplier_raw)
        line_item_normalized = normalize_line_item(line_item_raw)
        lookup_hash = build_lookup_hash(supplier_normalized, line_item_normalized)
        existing = next((row for row in self.rows if row.lookup_hash == lookup_hash), None)
        selected_reasoning = dict(reasoning or {})
        if selected_label:
            selected_reasoning.setdefault("selected_label", selected_label)
        if existing is None:
            row = LineItemSolution(
                id=f"mem-{len(self.rows) + 1}",
                lookup_hash=lookup_hash,
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                line_item_raw=line_item_raw,
                line_item_normalized=line_item_normalized,
                solved_for=[org_id],
                stable=False,
                unspsc_code=unspsc_code,
                unspsc_level=unspsc_level,
                policy_code=None,
                status_code="SOLVED",
                source_type="AGENTIC_MATCH",
                reasoning=selected_reasoning,
            ).recompute_stable()
            self.rows.append(row)
            return row
        solved_for = list(existing.solved_for)
        if existing.unspsc_code != unspsc_code:
            solved_for = [org_id]
        elif org_id not in solved_for:
            solved_for.append(org_id)
        row = LineItemSolution(
            id=existing.id,
            lookup_hash=lookup_hash,
            supplier_raw=supplier_raw,
            supplier_normalized=supplier_normalized,
            line_item_raw=line_item_raw,
            line_item_normalized=line_item_normalized,
            solved_for=solved_for,
            stable=False,
            unspsc_code=unspsc_code,
            unspsc_level=unspsc_level,
            policy_code=None,
            status_code="SOLVED",
            source_type="AGENTIC_MATCH",
            reasoning=selected_reasoning,
        ).recompute_stable()
        self.rows = [row if value.lookup_hash == lookup_hash else value for value in self.rows]
        return row


class InMemoryNonUnspscRuleRepository:
    def __init__(self, rows: Optional[List[NonUnspscRule]] = None):
        self.rows = sorted((rows or []), key=lambda row: row.rule_order)

    def find_first_match(self, line_item_text: str) -> Optional[NonUnspscRule]:
        for row in self.rows:
            if not row.active:
                continue
            if re.search(row.pattern, line_item_text, flags=re.IGNORECASE):
                return row
        return None


class PostgresLineItemSolutionRepository:
    def __init__(self, session: Session):
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("sqlalchemy is required for Postgres repositories")
        self.session = session

    def find_unstable(self, lookup_hash: str, org_id: str) -> Optional[LineItemSolution]:
        org_uuid = UUID(org_id)
        rows = (
            self.session.query(LipV2LineItemSolution)
            .filter(
                LipV2LineItemSolution.lookup_hash == lookup_hash,
                LipV2LineItemSolution.stable.is_(False),
            )
            .order_by(desc(LipV2LineItemSolution.updated_at))
            .all()
        )
        for row in rows:
            if org_uuid in (row.solved_for or []):
                return _map_solution_row(row)
        return None

    def find_stable(self, lookup_hash: str) -> Optional[LineItemSolution]:
        row = (
            self.session.query(LipV2LineItemSolution)
            .filter(
                LipV2LineItemSolution.lookup_hash == lookup_hash,
                LipV2LineItemSolution.stable.is_(True),
            )
            .order_by(desc(LipV2LineItemSolution.updated_at))
            .first()
        )
        return _map_solution_row(row) if row is not None else None

    def upsert_agentic_solution(
        self,
        *,
        org_id: str,
        supplier_raw: str,
        line_item_raw: str,
        unspsc_code: str,
        unspsc_level: str,
        reasoning: Optional[dict] = None,
        selected_label: Optional[str] = None,
    ) -> LineItemSolution:
        supplier_normalized = normalize_supplier(supplier_raw)
        line_item_normalized = normalize_line_item(line_item_raw)
        lookup_hash = build_lookup_hash(supplier_normalized, line_item_normalized)
        org_uuid = UUID(org_id)
        row = (
            self.session.query(LipV2LineItemSolution)
            .filter(LipV2LineItemSolution.lookup_hash == lookup_hash)
            .first()
        )
        selected_reasoning = dict(reasoning or {})
        if selected_label:
            selected_reasoning.setdefault("selected_label", selected_label)
        if row is None:
            row = LipV2LineItemSolution(
                lookup_hash=lookup_hash,
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                line_item_raw=line_item_raw,
                line_item_normalized=line_item_normalized,
                solved_for=[org_uuid],
                stable=False,
                unspsc_code=unspsc_code,
                unspsc_level=unspsc_level,
                policy_code=None,
                status_code="SOLVED",
                source_type="AGENTIC_MATCH",
                reasoning=selected_reasoning,
            )
            row.stable = len(set(row.solved_for or [])) >= 3
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            return _map_solution_row(row)

        solved_for = list(row.solved_for or [])
        if row.unspsc_code != unspsc_code:
            solved_for = [org_uuid]
        elif org_uuid not in solved_for:
            solved_for.append(org_uuid)
        row.supplier_raw = supplier_raw
        row.supplier_normalized = supplier_normalized
        row.line_item_raw = line_item_raw
        row.line_item_normalized = line_item_normalized
        row.solved_for = solved_for
        row.stable = len(set(solved_for)) >= 3
        row.unspsc_code = unspsc_code
        row.unspsc_level = unspsc_level
        row.policy_code = None
        row.status_code = "SOLVED"
        row.source_type = "AGENTIC_MATCH"
        row.reasoning = selected_reasoning
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _map_solution_row(row)


class PostgresNonUnspscRuleRepository:
    def __init__(self, session: Session):
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("sqlalchemy is required for Postgres repositories")
        self.session = session

    def find_first_match(self, line_item_text: str) -> Optional[NonUnspscRule]:
        rows = (
            self.session.query(LipV2NonUnspscRule)
            .filter(LipV2NonUnspscRule.active.is_(True))
            .order_by(LipV2NonUnspscRule.rule_order.asc())
            .all()
        )
        for row in rows:
            if re.search(row.pattern, line_item_text, flags=re.IGNORECASE):
                return _map_rule_row(row)
        return None


class PostgresCompanyEnrichmentRepository:
    def __init__(self, session: Session):
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("sqlalchemy is required for Postgres repositories")
        self.session = session

    def find_by_companies_house_number(self, companies_house_number: str):
        return (
            self.session.query(LipV2CompanyEnrichment)
            .filter(LipV2CompanyEnrichment.companies_house_number == companies_house_number)
            .first()
        )

    def find_by_company_name_normalized(self, company_name_normalized: str):
        return (
            self.session.query(LipV2CompanyEnrichment)
            .filter(
                or_(
                    LipV2CompanyEnrichment.company_name_normalized == company_name_normalized,
                    LipV2CompanyEnrichment.previous_names_normalized.any(company_name_normalized),
                )
            )
            .first()
        )

    def upsert_company(
        self,
        *,
        company_name_raw: str,
        company_name_normalized: str,
        companies_house_number: str,
        sic_codes: List[str],
        sic_labels: List[str],
        previous_names: List[str],
        previous_names_normalized: List[str],
        company_status: Optional[str],
        company_category: Optional[str],
        country_of_origin: Optional[str],
        incorporation_date,
        dissolution_date,
        vat_number: Optional[str],
        source_month: str,
        source_file_name: Optional[str],
    ):
        row = self.find_by_companies_house_number(companies_house_number)
        if row is None:
            row = LipV2CompanyEnrichment(
                company_name_raw=company_name_raw,
                company_name_normalized=company_name_normalized,
                companies_house_number=companies_house_number,
                sic_codes=list(sic_codes),
                sic_labels=list(sic_labels),
                previous_names=list(previous_names),
                previous_names_normalized=list(previous_names_normalized),
                company_status=company_status,
                company_category=company_category,
                country_of_origin=country_of_origin,
                incorporation_date=incorporation_date,
                dissolution_date=dissolution_date,
                vat_number=vat_number,
                source_month=source_month,
                source_file_name=source_file_name,
            )
        else:
            row.company_name_raw = company_name_raw
            row.company_name_normalized = company_name_normalized
            row.sic_codes = list(sic_codes)
            row.sic_labels = list(sic_labels)
            row.previous_names = list(previous_names)
            row.previous_names_normalized = list(previous_names_normalized)
            row.company_status = company_status
            row.company_category = company_category
            row.country_of_origin = country_of_origin
            row.incorporation_date = incorporation_date
            row.dissolution_date = dissolution_date
            row.vat_number = vat_number
            row.source_month = source_month
            row.source_file_name = source_file_name
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def find_best_fuzzy_match(self, company_name_normalized: str, min_similarity: float):
        result = self.session.execute(
            text(
                """
            WITH direct_candidates AS (
                SELECT
                    id,
                    GREATEST(similarity(company_name_normalized, :query), 0) AS match_score,
                    CASE
                        WHEN company_name_normalized % :query THEN 'fuzzy_current_name'
                        ELSE 'similar_current_name'
                    END AS match_method
                FROM lip_v2_company_enrichment
                WHERE
                    company_name_normalized % :query
                    OR similarity(company_name_normalized, :query) >= :min_similarity
            ),
            previous_name_candidates AS (
                SELECT
                    company.id,
                    MAX(similarity(previous_name, :query)) AS match_score,
                    'fuzzy_previous_name' AS match_method
                FROM lip_v2_company_enrichment AS company,
                LATERAL unnest(COALESCE(company.previous_names_normalized, ARRAY[]::text[])) AS previous_name
                WHERE
                    previous_name % :query
                    OR similarity(previous_name, :query) >= :min_similarity
                GROUP BY company.id
            ),
            ranked AS (
                SELECT * FROM direct_candidates
                UNION ALL
                SELECT * FROM previous_name_candidates
            )
            SELECT company.id, ranked.match_score, ranked.match_method
            FROM ranked
            JOIN lip_v2_company_enrichment AS company ON company.id = ranked.id
            ORDER BY ranked.match_score DESC, company.updated_at DESC
            LIMIT 1
            """
            ),
            {
                "query": company_name_normalized,
                "min_similarity": min_similarity,
            },
        ).mappings().first()
        if result is None:
            return None
        row = self.session.query(LipV2CompanyEnrichment).filter(LipV2CompanyEnrichment.id == result["id"]).first()
        if row is None:
            return None
        return row, float(result["match_score"] or 0.0), str(result["match_method"])


class PostgresSupplierCompanyMatchRepository:
    def __init__(self, session: Session):
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("sqlalchemy is required for Postgres repositories")
        self.session = session

    def find_by_supplier_normalized(self, supplier_normalized: str):
        return (
            self.session.query(LipV2SupplierCompanyMatch)
            .filter(LipV2SupplierCompanyMatch.supplier_normalized == supplier_normalized)
            .first()
        )

    def upsert_match(
        self,
        *,
        supplier_raw: str,
        supplier_normalized: str,
        companies_house_number: str,
        match_method: str,
        match_confidence: float,
    ):
        row = self.find_by_supplier_normalized(supplier_normalized)
        if row is None:
            row = LipV2SupplierCompanyMatch(
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                companies_house_number=companies_house_number,
                match_method=match_method,
                match_confidence=match_confidence,
            )
        else:
            row.supplier_raw = supplier_raw
            row.companies_house_number = companies_house_number
            row.match_method = match_method
            row.match_confidence = match_confidence
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row


def _map_solution_row(row: LipV2LineItemSolution) -> LineItemSolution:
    return LineItemSolution(
        id=str(row.id),
        lookup_hash=row.lookup_hash,
        supplier_raw=row.supplier_raw,
        supplier_normalized=row.supplier_normalized,
        line_item_raw=row.line_item_raw,
        line_item_normalized=row.line_item_normalized,
        solved_for=[str(org_id) for org_id in (row.solved_for or [])],
        stable=bool(row.stable),
        unspsc_code=row.unspsc_code,
        unspsc_level=row.unspsc_level,
        policy_code=row.policy_code,
        status_code=row.status_code,
        source_type=row.source_type,
        reasoning=row.reasoning or {},
    )


def _map_rule_row(row: LipV2NonUnspscRule) -> NonUnspscRule:
    return NonUnspscRule(
        id=str(row.id),
        rule_order=row.rule_order,
        label=row.label,
        pattern=row.pattern,
        policy_code=row.policy_code,
        status_code=row.status_code,
        fallback_unspsc_code=row.fallback_unspsc_code,
        fallback_unspsc_level=row.fallback_unspsc_level,
        active=bool(row.active),
    )
