import csv
import sys
import tempfile
import unittest
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.enrichment.importer import CompaniesHouseBulkImporter, iter_companies_house_rows
from app.enrichment.models import SupplierEnrichmentResult
from app.enrichment.service import SupplierEnrichmentService


class FakeCompanyRepo:
    def __init__(self):
        self.by_number = {}
        self.by_name = {}

    def find_by_companies_house_number(self, companies_house_number: str):
        return self.by_number.get(companies_house_number)

    def find_by_company_name_normalized(self, company_name_normalized: str):
        return self.by_name.get(company_name_normalized)

    def find_best_fuzzy_match(self, company_name_normalized: str, min_similarity: float):
        best_row = None
        best_score = 0.0
        best_method = None
        for normalized_name, row in self.by_name.items():
            score = SequenceMatcher(None, company_name_normalized, normalized_name).ratio()
            if score < min_similarity or score <= best_score:
                continue
            best_row = row
            best_score = score
            best_method = (
                "fuzzy_current_name"
                if normalized_name == row.company_name_normalized
                else "fuzzy_previous_name"
            )
        if best_row is None:
            return None
        return best_row, best_score, best_method

    def upsert_company(
        self,
        *,
        company_name_raw,
        company_name_normalized,
        companies_house_number,
        sic_codes,
        sic_labels,
        previous_names,
        previous_names_normalized,
        company_status,
        company_category,
        country_of_origin,
        incorporation_date,
        dissolution_date,
        vat_number,
        source_month,
        source_file_name,
    ):
        row = type(
            "CompanyRow",
            (),
            {
                "company_name_raw": company_name_raw,
                "company_name_normalized": company_name_normalized,
                "companies_house_number": companies_house_number,
                "sic_codes": list(sic_codes),
                "sic_labels": list(sic_labels),
                "previous_names": list(previous_names),
                "previous_names_normalized": list(previous_names_normalized),
                "company_status": company_status,
                "company_category": company_category,
                "country_of_origin": country_of_origin,
                "incorporation_date": incorporation_date,
                "dissolution_date": dissolution_date,
                "vat_number": vat_number,
                "source_month": source_month,
                "source_file_name": source_file_name,
            },
        )()
        self.by_number[companies_house_number] = row
        self.by_name[company_name_normalized] = row
        for previous_name_normalized in previous_names_normalized:
            self.by_name[previous_name_normalized] = row
        return row


class FakeSupplierMatchRepo:
    def __init__(self):
        self.by_supplier = {}

    def find_by_supplier_normalized(self, supplier_normalized: str):
        return self.by_supplier.get(supplier_normalized)

    def upsert_match(
        self,
        *,
        supplier_raw,
        supplier_normalized,
        companies_house_number,
        match_method,
        match_confidence,
    ):
        row = type(
            "MatchRow",
            (),
            {
                "supplier_raw": supplier_raw,
                "supplier_normalized": supplier_normalized,
                "companies_house_number": companies_house_number,
                "match_method": match_method,
                "match_confidence": match_confidence,
            },
        )()
        self.by_supplier[supplier_normalized] = row
        return row


class FakeBulkRepo:
    def __init__(self):
        self.rows = []

    def upsert_company(self, **kwargs):
        self.rows.append(kwargs)


class FakeSession:
    pass


class EnrichmentTests(unittest.TestCase):
    def test_iter_companies_house_rows_reads_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "companies.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["company_name", "companies_house_number", "sic_codes", "sic_labels"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "company_name": "Acme Ltd",
                        "companies_house_number": "12345678",
                        "sic_codes": "62012;62020",
                        "sic_labels": "Business software development;Information technology consultancy activities",
                    }
                )

            rows = list(iter_companies_house_rows(str(path)))

        self.assertEqual(rows[0]["company_name"], "Acme Ltd")
        self.assertEqual(rows[0]["companies_house_number"], "12345678")

    def test_iter_companies_house_rows_strips_spaced_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "companies.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write("CompanyName, CompanyNumber, SICCode.SicText_1\n")
                handle.write("Acme Ltd,12345678,62012 - Business software development\n")

            rows = list(iter_companies_house_rows(str(path)))

        self.assertEqual(rows[0]["CompanyName"], "Acme Ltd")
        self.assertEqual(rows[0]["CompanyNumber"], "12345678")
        self.assertEqual(rows[0]["SICCode.SicText_1"], "62012 - Business software development")

    def test_supplier_enrichment_service_exact_name_match_returns_sic(self):
        company_repo = FakeCompanyRepo()
        company_repo.upsert_company(
            company_name_raw="Acme Ltd",
            company_name_normalized="acme ltd",
            companies_house_number="12345678",
            sic_codes=["62012"],
            sic_labels=["Business software development"],
            previous_names=[],
            previous_names_normalized=[],
            company_status="Active",
            company_category="Private Limited Company",
            country_of_origin="United Kingdom",
            incorporation_date=None,
            dissolution_date=None,
            vat_number=None,
            source_month="2026-07",
            source_file_name="companies.csv",
        )
        match_repo = FakeSupplierMatchRepo()
        service = SupplierEnrichmentService(company_repo=company_repo, supplier_match_repo=match_repo)

        result = service.enrich_supplier("Acme Ltd")

        self.assertEqual(result.companies_house_number, "12345678")
        self.assertEqual(result.supplier_sic_label, "Business software development")
        self.assertEqual(result.match_method, "exact_normalized_name")

    def test_supplier_enrichment_service_matches_previous_company_name(self):
        company_repo = FakeCompanyRepo()
        company_repo.upsert_company(
            company_name_raw="Acme Ltd",
            company_name_normalized="acme ltd",
            companies_house_number="12345678",
            sic_codes=["62012"],
            sic_labels=["Business software development"],
            previous_names=["Acme Software Ltd"],
            previous_names_normalized=["acme software ltd"],
            company_status="Active",
            company_category="Private Limited Company",
            country_of_origin="United Kingdom",
            incorporation_date=None,
            dissolution_date=None,
            vat_number=None,
            source_month="2026-07",
            source_file_name="companies.csv",
        )
        match_repo = FakeSupplierMatchRepo()
        service = SupplierEnrichmentService(company_repo=company_repo, supplier_match_repo=match_repo)

        result = service.enrich_supplier("Acme Software Ltd")

        self.assertEqual(result.companies_house_number, "12345678")
        self.assertEqual(result.company_name, "Acme Ltd")
        self.assertEqual(result.supplier_sic_label, "Business software development")

    def test_supplier_enrichment_service_uses_fuzzy_match_when_exact_match_misses(self):
        company_repo = FakeCompanyRepo()
        company_repo.upsert_company(
            company_name_raw="The Little Field Court Management Company Limited",
            company_name_normalized="the little field court management company limited",
            companies_house_number="7141194",
            sic_codes=["70100"],
            sic_labels=["Activities of head offices"],
            previous_names=[],
            previous_names_normalized=[],
            company_status="Active",
            company_category="PRI LTD BY GUAR NSC",
            country_of_origin="United Kingdom",
            incorporation_date=None,
            dissolution_date=None,
            vat_number=None,
            source_month="2026-07",
            source_file_name="companies.csv",
        )
        match_repo = FakeSupplierMatchRepo()
        service = SupplierEnrichmentService(
            company_repo=company_repo,
            supplier_match_repo=match_repo,
            min_similarity=0.60,
        )

        result = service.enrich_supplier("Little Field Court Mgmt Co Ltd")

        self.assertEqual(result.companies_house_number, "7141194")
        self.assertEqual(result.company_name, "The Little Field Court Management Company Limited")
        self.assertEqual(result.match_method, "fuzzy_current_name")
        self.assertGreaterEqual(result.match_confidence, 0.60)
        self.assertEqual(
            match_repo.by_supplier["little field court mgmt co ltd"].companies_house_number,
            "7141194",
        )

    def test_companies_house_importer_parses_real_companies_house_shape(self):
        repo = FakeBulkRepo()
        importer = CompaniesHouseBulkImporter(repo=repo)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "companies.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "CompanyName",
                        "CompanyNumber",
                        "CompanyCategory",
                        "CompanyStatus",
                        "CountryOfOrigin",
                        "DissolutionDate",
                        "IncorporationDate",
                        "SICCode.SicText_1",
                        "SICCode.SicText_2",
                        "SICCode.SicText_3",
                        "SICCode.SicText_4",
                        "PreviousName_1.CompanyName",
                        "PreviousName_2.CompanyName",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "CompanyName": "Acme Ltd",
                        "CompanyNumber": "12345678",
                        "CompanyCategory": "Private Limited Company",
                        "CompanyStatus": "Active",
                        "CountryOfOrigin": "United Kingdom",
                        "DissolutionDate": "",
                        "IncorporationDate": "04/04/2017",
                        "SICCode.SicText_1": "62012 - Business software development",
                        "SICCode.SicText_2": "62020 - Information technology consultancy activities",
                        "SICCode.SicText_3": "",
                        "SICCode.SicText_4": "",
                        "PreviousName_1.CompanyName": "Acme Software Ltd",
                        "PreviousName_2.CompanyName": "Acme Consulting Ltd",
                    }
                )

            imported = importer.import_file(path=str(path), source_month="2026-07")

        self.assertEqual(imported, 1)
        self.assertEqual(repo.rows[0]["company_name_normalized"], "acme ltd")
        self.assertEqual(repo.rows[0]["sic_codes"], ["62012", "62020"])
        self.assertEqual(
            repo.rows[0]["sic_labels"],
            [
                "Business software development",
                "Information technology consultancy activities",
            ],
        )
        self.assertEqual(
            repo.rows[0]["previous_names"],
            ["Acme Software Ltd", "Acme Consulting Ltd"],
        )
        self.assertEqual(
            repo.rows[0]["previous_names_normalized"],
            ["acme software ltd", "acme consulting ltd"],
        )
        self.assertEqual(repo.rows[0]["company_status"], "Active")
        self.assertEqual(repo.rows[0]["company_category"], "Private Limited Company")
        self.assertEqual(repo.rows[0]["country_of_origin"], "United Kingdom")
        self.assertEqual(repo.rows[0]["incorporation_date"], date(2017, 4, 4))

    def test_companies_house_importer_emits_progress_logs(self):
        repo = FakeBulkRepo()
        messages = []
        importer = CompaniesHouseBulkImporter(repo=repo, progress_logger=messages.append)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "companies.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["CompanyName", "CompanyNumber", "SICCode.SicText_1"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "CompanyName": "Acme Ltd",
                        "CompanyNumber": "12345678",
                        "SICCode.SicText_1": "62012 - Business software development",
                    }
                )
                writer.writerow(
                    {
                        "CompanyName": "Bravo Ltd",
                        "CompanyNumber": "87654321",
                        "SICCode.SicText_1": "62020 - Information technology consultancy activities",
                    }
                )

            imported = importer.import_file(
                path=str(path),
                source_month="2026-07",
                progress_every=1,
            )

        self.assertEqual(imported, 2)
        self.assertTrue(messages[0].startswith("[companies-house-import] starting"))
        self.assertTrue(any("progress scanned=1 imported=1" in message for message in messages))
        self.assertTrue(any("progress scanned=2 imported=2" in message for message in messages))
        self.assertTrue(messages[-1].startswith("[companies-house-import] completed"))


if __name__ == "__main__":
    unittest.main()
