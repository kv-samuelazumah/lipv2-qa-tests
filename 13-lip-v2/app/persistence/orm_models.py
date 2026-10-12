from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql.sqltypes import String


Base = declarative_base()
UNSPSC_EMBEDDING_DIMENSIONS = 3072


class LipV2LineItemSolution(Base):
    __tablename__ = "lip_v2_line_item_solution"
    __table_args__ = (
        UniqueConstraint("lookup_hash", name="uq_lip_v2_line_item_solution_lookup_hash"),
        CheckConstraint(
            "(unspsc_code IS NULL OR unspsc_code ~ '^[0-9]{4,8}$')",
            name="chk_lip_v2_unspsc_code_format",
        ),
        CheckConstraint(
            "((stable = false AND cardinality(solved_for) < 3) "
            "OR (stable = true AND cardinality(solved_for) >= 3))",
            name="chk_lip_v2_stable_matches_solved_for",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lookup_hash = Column(Text, nullable=False, index=True)
    supplier_raw = Column(Text, nullable=False)
    supplier_normalized = Column(Text, nullable=False)
    line_item_raw = Column(Text, nullable=False)
    line_item_normalized = Column(Text, nullable=False)
    stable = Column(Boolean, nullable=False, default=False, index=True)
    solved_for = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    unspsc_code = Column(String(8), nullable=True)
    unspsc_level = Column(String(32), nullable=True)
    policy_code = Column(Text, nullable=True)
    status_code = Column(Text, nullable=False)
    source_type = Column(String(32), nullable=False)
    reasoning = Column(JSONB, nullable=True)
    first_solved_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_solved_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LipV2NonUnspscRule(Base):
    __tablename__ = "lip_v2_non_unspsc_rules"
    __table_args__ = (
        UniqueConstraint("rule_order", name="uq_lip_v2_non_unspsc_rule_order"),
        CheckConstraint(
            "(fallback_unspsc_code IS NULL OR fallback_unspsc_code ~ '^-?[0-9]{4,8}$')",
            name="chk_lip_v2_non_unspsc_fallback_code_format",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_order = Column(Integer, nullable=False)
    label = Column(Text, nullable=False)
    pattern = Column(Text, nullable=False)
    policy_code = Column(Text, nullable=False)
    status_code = Column(Text, nullable=False)
    fallback_unspsc_code = Column(String(8), nullable=True)
    fallback_unspsc_level = Column(String(32), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LipV2UnspscEmbedding(Base):
    __tablename__ = "lip_v2_unspsc_embeddings_v2"
    __table_args__ = (
        UniqueConstraint(
            "unspsc_release_version",
            "level",
            "segment_code",
            "family_code",
            "class_code",
            "commodity_code",
            name="uq_lip_v2_unspsc_embeddings_identity",
        ),
        CheckConstraint(
            "level IN ('SEGMENT', 'FAMILY', 'CLASS', 'COMMODITY')",
            name="chk_lip_v2_unspsc_level",
        ),
        CheckConstraint(
            "((is_leaf = true AND commodity_code IS NOT NULL) OR (is_leaf = false))",
            name="chk_lip_v2_unspsc_leaf_consistency",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unspsc_release_version = Column(Text, nullable=False, index=True)
    level = Column(String(32), nullable=False, index=True)
    path = Column(Text, nullable=False)
    parent_code = Column(String(8), nullable=True)
    is_leaf = Column(Boolean, nullable=False, default=False)
    commodity_title = Column(Text, nullable=True)
    commodity_code = Column(String(8), nullable=True, index=True)
    class_title = Column(Text, nullable=True)
    class_code = Column(String(8), nullable=True, index=True)
    family_title = Column(Text, nullable=True)
    family_code = Column(String(8), nullable=True, index=True)
    segment_title = Column(Text, nullable=False)
    segment_code = Column(String(8), nullable=False, index=True)
    synonyms = Column(ARRAY(Text), nullable=False, default=list)
    examples = Column(ARRAY(Text), nullable=False, default=list)
    search_document = Column(Text, nullable=False)
    embedding_text = Column(Text, nullable=False)
    embedding = Column(Vector(UNSPSC_EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model = Column(String(64), nullable=False)
    embedding_version = Column(Integer, nullable=False, default=1)
    embedding_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LipV2CompanyEnrichment(Base):
    __tablename__ = "lip_v2_company_enrichment"
    __table_args__ = (
        UniqueConstraint("companies_house_number", name="uq_lip_v2_company_enrichment_ch_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name_raw = Column(Text, nullable=False)
    company_name_normalized = Column(Text, nullable=False, index=True)
    companies_house_number = Column(String(16), nullable=False, index=True)
    sic_codes = Column(ARRAY(Text), nullable=False, default=list)
    sic_labels = Column(ARRAY(Text), nullable=False, default=list)
    previous_names = Column(ARRAY(Text), nullable=False, default=list)
    previous_names_normalized = Column(ARRAY(Text), nullable=False, default=list)
    company_status = Column(Text, nullable=True)
    company_category = Column(Text, nullable=True)
    country_of_origin = Column(Text, nullable=True)
    incorporation_date = Column(Date, nullable=True)
    dissolution_date = Column(Date, nullable=True)
    vat_number = Column(Text, nullable=True)
    source_month = Column(String(16), nullable=False, index=True)
    source_file_name = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LipV2SupplierCompanyMatch(Base):
    __tablename__ = "lip_v2_supplier_company_match"
    __table_args__ = (
        UniqueConstraint("supplier_normalized", name="uq_lip_v2_supplier_company_match_supplier_normalized"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_raw = Column(Text, nullable=False)
    supplier_normalized = Column(Text, nullable=False, index=True)
    companies_house_number = Column(String(16), nullable=False, index=True)
    match_method = Column(String(64), nullable=False)
    match_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
