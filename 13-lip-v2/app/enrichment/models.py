from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SupplierEnrichmentResult:
    supplier_raw: str
    supplier_normalized: str
    companies_house_number: Optional[str] = None
    company_name: Optional[str] = None
    sic_codes: List[str] = field(default_factory=list)
    sic_labels: List[str] = field(default_factory=list)
    vat_number: Optional[str] = None
    match_method: Optional[str] = None
    match_confidence: Optional[float] = None

    @property
    def supplier_sic_label(self) -> Optional[str]:
        if not self.sic_labels:
            return None
        return " | ".join(self.sic_labels)
