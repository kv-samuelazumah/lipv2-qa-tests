from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from app.pipeline.models import LineItemPipelineInput
from app.pipeline.service import LineItemPipelineService

if TYPE_CHECKING:
    from app.persistence.database import Database


def main() -> None:
    from app.enrichment.importer import CompaniesHouseBulkImporter
    from app.persistence.database import Database
    from app.persistence.seed import NonUnspscRuleSeeder, StableLookupSeeder, UnstableLookupSeeder
    from app.pre_agentic.service import PreAgenticService
    from app.search.importer import UnspscCorpusImporter
    from app.worker.runtime import LineItemWorker

    args = _parse_args()
    db = Database()
    try:
        db.init_db()
        seeded = None
        if db.db_config.seed_non_unspsc_rules:
            session = db.get_session()
            try:
                seeded = NonUnspscRuleSeeder(session).seed()
            finally:
                session.close()
        print(
            f"13-lip-v2 database initialized (schema_sync={'on' if db.db_config.schema_sync else 'off'})"
        )
        if seeded is not None:
            print(f"Seeded {seeded} non-UNSPSC rules")
        if db.db_config.seed_stable_lookups:
            session = db.get_session()
            try:
                stable_seeded = StableLookupSeeder(session).seed()
            finally:
                session.close()
            print(f"Seeded {stable_seeded} new stable lookup entries")
        if db.db_config.seed_unstable_lookups:
            session = db.get_session()
            try:
                unstable_seeded = UnstableLookupSeeder(session).seed()
            finally:
                session.close()
            print(f"Seeded {unstable_seeded} new unstable lookup entries")
        if args.index_unspsc_corpus:
            imported = UnspscCorpusImporter().import_file(args.index_unspsc_corpus)
            print(json.dumps({"indexed_documents": imported, "corpus_path": args.index_unspsc_corpus}))
            return
        if args.import_companies_house:
            if not args.companies_house_source_month:
                raise ValueError("--companies-house-source-month is required with --import-companies-house")
            session = db.get_session()
            try:
                imported = CompaniesHouseBulkImporter(session=session).import_file(
                    path=args.import_companies_house,
                    source_month=args.companies_house_source_month,
                    company_name_column=args.companies_house_company_name_column,
                    companies_house_number_column=args.companies_house_number_column,
                    sic_codes_column=args.companies_house_sic_codes_column,
                    sic_labels_column=args.companies_house_sic_labels_column,
                    vat_number_column=args.companies_house_vat_column,
                    progress_every=args.companies_house_progress_every,
                )
            finally:
                session.close()
            print(
                json.dumps(
                    {
                        "imported_companies": imported,
                        "source_month": args.companies_house_source_month,
                        "path": args.import_companies_house,
                    }
                )
            )
            return
        if args.bootstrap_only:
            return
        if args.input_json:
            pipeline = _build_pipeline(db)
            results = _run_input_json(
                pipeline,
                args.input_json,
                run_until_stage=args.run_until_stage,
                skip_pre_agentic=args.skip_pre_agentic,
            )
            print(json.dumps(results))
            return
        if args.org_id and args.supplier and args.line_item:
            service = PreAgenticService(db)
            result = service.resolve(
                org_id=args.org_id,
                supplier_raw=args.supplier,
                line_item_raw=args.line_item,
            )
            print(json.dumps(result))
            return
        worker = LineItemWorker(pipeline=_build_pipeline(db))
        try:
            worker.run_forever()
        finally:
            worker.close()
    finally:
        db.close()


def _parse_args():
    parser = argparse.ArgumentParser(description="Initialize and run 13-lip-v2 pre-agentic resolution")
    parser.add_argument("--bootstrap-only", action="store_true")
    parser.add_argument("--input-json")
    parser.add_argument("--org-id", dest="org_id")
    parser.add_argument("--supplier")
    parser.add_argument("--line-item", dest="line_item")
    parser.add_argument("--index-unspsc-corpus", dest="index_unspsc_corpus")
    parser.add_argument("--import-companies-house", dest="import_companies_house")
    parser.add_argument("--companies-house-source-month", dest="companies_house_source_month")
    parser.add_argument(
        "--companies-house-company-name-column",
        dest="companies_house_company_name_column",
        default="CompanyName",
    )
    parser.add_argument(
        "--companies-house-number-column",
        dest="companies_house_number_column",
        default="CompanyNumber",
    )
    parser.add_argument(
        "--companies-house-sic-codes-column",
        dest="companies_house_sic_codes_column",
        default="sic_codes",
    )
    parser.add_argument(
        "--companies-house-sic-labels-column",
        dest="companies_house_sic_labels_column",
        default="sic_labels",
    )
    parser.add_argument("--companies-house-vat-column", dest="companies_house_vat_column")
    parser.add_argument(
        "--companies-house-progress-every",
        dest="companies_house_progress_every",
        type=int,
        default=10000,
    )
    parser.add_argument(
        "--run-until-stage",
        choices=["pre_agentic", "identify", "search", "evaluate", "web_search", "web_reidentify", "full"],
        default="full",
    )
    parser.add_argument("--skip-pre-agentic", action="store_true")
    return parser.parse_args()


def _run_input_json(
    pipeline: LineItemPipelineService,
    raw_input: str,
    *,
    run_until_stage: str,
    skip_pre_agentic: bool,
):
    payload = json.loads(raw_input)
    if isinstance(payload, list):
        return [
            _resolve_payload_item_safe(
                pipeline=pipeline,
                payload=item,
                index=index,
                run_until_stage=run_until_stage,
                skip_pre_agentic=skip_pre_agentic,
            )
            for index, item in enumerate(payload)
        ]
    return _resolve_payload_item(
        pipeline,
        payload,
        run_until_stage=run_until_stage,
        skip_pre_agentic=skip_pre_agentic,
    )


def _resolve_payload_item(
    pipeline: LineItemPipelineService,
    payload: dict,
    *,
    run_until_stage: str,
    skip_pre_agentic: bool,
):
    org_id = _pick_first(
        payload,
        "orgId",
        "org_id",
    )
    if not org_id:
        raise ValueError("input JSON must include orgId or org_id")

    supplier_raw = _pick_first(
        payload,
        "supplier",
        "supplierRaw",
        "supplier_raw",
        "vendorName",
        "vendor_name",
        "counterparty",
        "counterpartyName",
    ) or ""

    line_item_raw = _pick_first(
        payload,
        "lineItemText",
        "line_item_text",
        "lineItemRaw",
        "line_item_raw",
        "description",
    )
    if not line_item_raw:
        raise ValueError(
            "input JSON must include one of: lineItemText, line_item_text, lineItemRaw, line_item_raw, description"
        )

    result = pipeline.process(
        LineItemPipelineInput(
            org_id=str(org_id),
            supplier_raw=str(supplier_raw),
            line_item_raw=str(line_item_raw),
            cleaned_line_item=_pick_first(payload, "cleanedLineItem", "cleaned_line_item", "description_clean"),
            unit_of_measure_raw=_pick_first(payload, "unitOfMeasurement", "unit_of_measure_raw", "unit_of_measure"),
            quantity=_pick_number(payload, "quantity"),
            unit_price=_pick_number(payload, "unitPrice", "unit_price"),
            line_subtotal=_pick_number(payload, "lineSubtotal", "line_subtotal", "lineItemSubTotal"),
            unspsc_ready_invoice_description=_pick_first(
                payload,
                "unspscReadyInvoiceDescription",
                "unspsc_ready_invoice_description",
            ),
            supplier_sic_label=_pick_first(payload, "supplierSicLabel", "supplier_sic_label"),
            buyer_sic_label=_pick_first(payload, "buyerSicLabel", "buyer_sic_label"),
            house_rules=payload.get("houseRules", payload.get("house_rules", [])) or [],
        ),
        run_until_stage=run_until_stage,
        skip_pre_agentic=skip_pre_agentic,
    ).as_dict()
    return {
        "input": {
            "org_id": str(org_id),
            "supplier_raw": str(supplier_raw),
            "line_item_raw": str(line_item_raw),
        },
        "cli": {
            "run_until_stage": run_until_stage,
            "skip_pre_agentic": skip_pre_agentic,
        },
        "result": result,
    }


def _resolve_payload_item_safe(
    *,
    pipeline: LineItemPipelineService,
    payload: dict,
    index: int,
    run_until_stage: str,
    skip_pre_agentic: bool,
):
    try:
        return _resolve_payload_item(
            pipeline,
            payload,
            run_until_stage=run_until_stage,
            skip_pre_agentic=skip_pre_agentic,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "input": {
                "org_id": str(_pick_first(payload, "orgId", "org_id") or ""),
                "supplier_raw": str(
                    _pick_first(
                        payload,
                        "supplier",
                        "supplierRaw",
                        "supplier_raw",
                        "vendorName",
                        "vendor_name",
                        "counterparty",
                        "counterpartyName",
                    )
                    or ""
                ),
                "line_item_raw": str(
                    _pick_first(
                        payload,
                        "lineItemText",
                        "line_item_text",
                        "lineItemRaw",
                        "line_item_raw",
                        "description",
                    )
                    or ""
                ),
            },
            "cli": {
                "run_until_stage": run_until_stage,
                "skip_pre_agentic": skip_pre_agentic,
                "batch_index": index,
            },
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
            "result": None,
        }


def _build_pipeline(db: Database) -> LineItemPipelineService:
    from app.enrichment.service import DatabaseSupplierEnrichmentService
    from app.pre_agentic.service import PreAgenticService

    return LineItemPipelineService(
        pre_agentic_service=PreAgenticService(db),
        enrichment_service=DatabaseSupplierEnrichmentService(db),
    )


def _pick_first(payload: dict, *keys: str):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _pick_number(payload: dict, *keys: str):
    value = _pick_first(payload, *keys)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
