from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional

from ..pre_agentic.normalize import normalize_supplier
from ..persistence.repository import PostgresCompanyEnrichmentRepository


def iter_companies_house_rows(path: str) -> Iterator[dict]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".jsonl":
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    yield json.loads(stripped)
        return
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, skipinitialspace=True)
        for row in reader:
            yield {
                (key.strip() if isinstance(key, str) else key): value
                for key, value in dict(row).items()
            }


class CompaniesHouseBulkImporter:
    def __init__(self, session=None, repo=None, progress_logger: Optional[Callable[[str], None]] = None):
        if repo is not None:
            self.repo = repo
        elif session is None:
            raise ValueError("session is required when repo is not provided")
        else:
            self.repo = PostgresCompanyEnrichmentRepository(session)
        self.progress_logger = progress_logger or print

    def import_file(
        self,
        *,
        path: str,
        source_month: str,
        company_name_column: str = "CompanyName",
        companies_house_number_column: str = "CompanyNumber",
        sic_codes_column: str = "sic_codes",
        sic_labels_column: Optional[str] = "sic_labels",
        vat_number_column: Optional[str] = None,
        progress_every: int = 10_000,
    ) -> int:
        total = 0
        scanned = 0
        skipped = 0
        file_name = Path(path).name
        started_at = time.monotonic()
        self.progress_logger(
            f"[companies-house-import] starting file={file_name} source_month={source_month} progress_every={progress_every}"
        )
        for row in iter_companies_house_rows(path):
            scanned += 1
            company_name_raw = str(row.get(company_name_column) or "").strip()
            companies_house_number = str(row.get(companies_house_number_column) or "").strip()
            if not company_name_raw or not companies_house_number:
                skipped += 1
                if progress_every > 0 and scanned % progress_every == 0:
                    self._log_progress(scanned=scanned, imported=total, skipped=skipped, started_at=started_at)
                continue
            sic_codes, sic_labels = _extract_sic_details(
                row=row,
                sic_codes_column=sic_codes_column,
                sic_labels_column=sic_labels_column,
            )
            vat_number = None if not vat_number_column else _optional_str(row.get(vat_number_column))
            previous_names = _extract_previous_names(row)
            self.repo.upsert_company(
                company_name_raw=company_name_raw,
                company_name_normalized=normalize_supplier(company_name_raw),
                companies_house_number=companies_house_number,
                sic_codes=sic_codes,
                sic_labels=sic_labels,
                previous_names=previous_names,
                previous_names_normalized=[normalize_supplier(name) for name in previous_names],
                company_status=_optional_str(row.get("CompanyStatus")),
                company_category=_optional_str(row.get("CompanyCategory")),
                country_of_origin=_optional_str(row.get("CountryOfOrigin")),
                incorporation_date=_parse_companies_house_date(row.get("IncorporationDate")),
                dissolution_date=_parse_companies_house_date(row.get("DissolutionDate")),
                vat_number=vat_number,
                source_month=source_month,
                source_file_name=file_name,
            )
            total += 1
            if progress_every > 0 and scanned % progress_every == 0:
                self._log_progress(scanned=scanned, imported=total, skipped=skipped, started_at=started_at)
        elapsed_seconds = max(time.monotonic() - started_at, 0.001)
        self.progress_logger(
            "[companies-house-import] completed "
            f"scanned={scanned} imported={total} skipped={skipped} "
            f"elapsed={elapsed_seconds:.1f}s rate={total / elapsed_seconds:.1f} imported_rows_per_sec"
        )
        return total

    def _log_progress(self, *, scanned: int, imported: int, skipped: int, started_at: float) -> None:
        elapsed_seconds = max(time.monotonic() - started_at, 0.001)
        self.progress_logger(
            "[companies-house-import] progress "
            f"scanned={scanned} imported={imported} skipped={skipped} "
            f"elapsed={elapsed_seconds:.1f}s rate={imported / elapsed_seconds:.1f} imported_rows_per_sec"
        )


def _extract_sic_details(
    *,
    row: dict,
    sic_codes_column: str,
    sic_labels_column: Optional[str],
) -> tuple[list[str], list[str]]:
    if sic_codes_column in row or (sic_labels_column and sic_labels_column in row):
        sic_codes = _split_multi_value(row.get(sic_codes_column))
        sic_labels = _split_multi_value(row.get(sic_labels_column)) if sic_labels_column else []
        return sic_codes, sic_labels

    entries = []
    for index in range(1, 5):
        value = _optional_str(row.get(f"SICCode.SicText_{index}"))
        if value:
            entries.append(value)
    if not entries:
        return [], []

    sic_codes: list[str] = []
    sic_labels: list[str] = []
    for entry in entries:
        code, label = _split_companies_house_sic_entry(entry)
        if code:
            sic_codes.append(code)
        if label:
            sic_labels.append(label)
    return sic_codes, sic_labels


def _split_companies_house_sic_entry(entry: str) -> tuple[Optional[str], Optional[str]]:
    text = entry.strip()
    if not text:
        return None, None
    match = re.match(r"^\s*([0-9]{4,8})\s*-\s*(.+?)\s*$", text)
    if match:
        return match.group(1), match.group(2)
    digits = re.match(r"^\s*([0-9]{4,8})\s*$", text)
    if digits:
        return digits.group(1), None
    return None, text


def _extract_previous_names(row: dict) -> list[str]:
    previous_names: list[str] = []
    for index in range(1, 11):
        value = _optional_str(row.get(f"PreviousName_{index}.CompanyName"))
        if value:
            previous_names.append(value)
    return previous_names


def _parse_companies_house_date(value) -> Optional[datetime.date]:
    text = _optional_str(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def _split_multi_value(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    if "|" in raw:
        return [part.strip() for part in raw.split("|") if part.strip()]
    if ";" in raw:
        return [part.strip() for part in raw.split(";") if part.strip()]
    if "," in raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [raw]


def _optional_str(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
