from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..core.config import Config
from ..pre_agentic.normalize import normalize_supplier
from ..persistence.repository import CompanyEnrichmentRepository, SupplierCompanyMatchRepository
from .models import SupplierEnrichmentResult

if TYPE_CHECKING:
    from ..persistence.database import Database
    from sqlalchemy.orm import Session


class SupplierEnrichmentService:
    def __init__(
        self,
        company_repo: CompanyEnrichmentRepository,
        supplier_match_repo: SupplierCompanyMatchRepository,
        min_similarity: Optional[float] = None,
    ):
        self.company_repo = company_repo
        self.supplier_match_repo = supplier_match_repo
        self.min_similarity = (
            Config.get_supplier_match_min_similarity()
            if min_similarity is None
            else min_similarity
        )

    def enrich_supplier(self, supplier_raw: str) -> SupplierEnrichmentResult:
        supplier_normalized = normalize_supplier(supplier_raw)
        cached_match = self.supplier_match_repo.find_by_supplier_normalized(supplier_normalized)
        if cached_match is not None:
            company = self.company_repo.find_by_companies_house_number(cached_match.companies_house_number)
            if company is not None:
                return SupplierEnrichmentResult(
                    supplier_raw=supplier_raw,
                    supplier_normalized=supplier_normalized,
                    companies_house_number=company.companies_house_number,
                    company_name=company.company_name_raw,
                    sic_codes=company.sic_codes,
                    sic_labels=company.sic_labels,
                    vat_number=company.vat_number,
                    match_method=cached_match.match_method,
                    match_confidence=cached_match.match_confidence,
                )

        exact_company = self.company_repo.find_by_company_name_normalized(supplier_normalized)
        if exact_company is not None:
            self.supplier_match_repo.upsert_match(
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                companies_house_number=exact_company.companies_house_number,
                match_method="exact_normalized_name",
                match_confidence=1.0,
            )
            return SupplierEnrichmentResult(
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                companies_house_number=exact_company.companies_house_number,
                company_name=exact_company.company_name_raw,
                sic_codes=exact_company.sic_codes,
                sic_labels=exact_company.sic_labels,
                vat_number=exact_company.vat_number,
                match_method="exact_normalized_name",
                match_confidence=1.0,
            )

        fuzzy_match = self.company_repo.find_best_fuzzy_match(
            supplier_normalized,
            self.min_similarity,
        )
        if fuzzy_match is not None:
            company, match_confidence, match_method = fuzzy_match
            self.supplier_match_repo.upsert_match(
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                companies_house_number=company.companies_house_number,
                match_method=match_method,
                match_confidence=match_confidence,
            )
            return SupplierEnrichmentResult(
                supplier_raw=supplier_raw,
                supplier_normalized=supplier_normalized,
                companies_house_number=company.companies_house_number,
                company_name=company.company_name_raw,
                sic_codes=company.sic_codes,
                sic_labels=company.sic_labels,
                vat_number=company.vat_number,
                match_method=match_method,
                match_confidence=match_confidence,
            )

        return SupplierEnrichmentResult(
            supplier_raw=supplier_raw,
            supplier_normalized=supplier_normalized,
        )


class DatabaseSupplierEnrichmentService:
    def __init__(self, database: "Database"):
        self.database = database

    def enrich_supplier(self, supplier_raw: str) -> SupplierEnrichmentResult:
        from ..persistence.repository import (
            PostgresCompanyEnrichmentRepository,
            PostgresSupplierCompanyMatchRepository,
        )

        session: "Session" = self.database.get_session()
        try:
            service = SupplierEnrichmentService(
                company_repo=PostgresCompanyEnrichmentRepository(session),
                supplier_match_repo=PostgresSupplierCompanyMatchRepository(session),
            )
            return service.enrich_supplier(supplier_raw)
        finally:
            session.close()
