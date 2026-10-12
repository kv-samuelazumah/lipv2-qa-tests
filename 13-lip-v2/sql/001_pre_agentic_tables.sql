CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS lip_v2_line_item_solution (
    id uuid PRIMARY KEY,
    lookup_hash text NOT NULL,
    supplier_raw text NOT NULL,
    supplier_normalized text NOT NULL,
    line_item_raw text NOT NULL,
    line_item_normalized text NOT NULL,
    stable boolean NOT NULL DEFAULT false,
    solved_for uuid[] NOT NULL DEFAULT '{}',
    unspsc_code varchar(8) NULL,
    unspsc_level varchar(32) NULL,
    policy_code text NULL,
    status_code text NOT NULL,
    source_type varchar(32) NOT NULL,
    reasoning jsonb NULL,
    first_solved_at timestamptz NOT NULL DEFAULT now(),
    last_solved_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lip_v2_line_item_solution_lookup_hash UNIQUE (lookup_hash),
    CONSTRAINT chk_lip_v2_unspsc_code_format
        CHECK (unspsc_code IS NULL OR unspsc_code ~ '^[0-9]{4,8}$'),
    CONSTRAINT chk_lip_v2_stable_matches_solved_for
        CHECK (
            (stable = false AND cardinality(solved_for) < 3)
            OR
            (stable = true AND cardinality(solved_for) >= 3)
        )
);

CREATE INDEX IF NOT EXISTS idx_lip_v2_line_item_solution_lookup_hash
    ON lip_v2_line_item_solution (lookup_hash);

CREATE INDEX IF NOT EXISTS idx_lip_v2_line_item_solution_stable
    ON lip_v2_line_item_solution (stable);

CREATE INDEX IF NOT EXISTS idx_lip_v2_line_item_solution_solved_for
    ON lip_v2_line_item_solution USING gin (solved_for);

CREATE TABLE IF NOT EXISTS lip_v2_non_unspsc_rules (
    id uuid PRIMARY KEY,
    rule_order integer NOT NULL,
    label text NOT NULL,
    pattern text NOT NULL,
    policy_code text NOT NULL,
    status_code text NOT NULL,
    fallback_unspsc_code varchar(8) NULL,
    fallback_unspsc_level varchar(32) NULL,
    active boolean NOT NULL DEFAULT true,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lip_v2_non_unspsc_rule_order UNIQUE (rule_order),
    CONSTRAINT chk_lip_v2_non_unspsc_fallback_code_format
        CHECK (
            fallback_unspsc_code IS NULL
            OR fallback_unspsc_code ~ '^-?[0-9]{4,8}$'
        )
);

CREATE INDEX IF NOT EXISTS idx_lip_v2_non_unspsc_rules_active_order
    ON lip_v2_non_unspsc_rules (active, rule_order);

CREATE TABLE IF NOT EXISTS lip_v2_unspsc_embeddings_v2 (
    id uuid PRIMARY KEY,
    unspsc_release_version text NOT NULL,
    level varchar(32) NOT NULL,
    path text NOT NULL,
    parent_code varchar(8) NULL,
    is_leaf boolean NOT NULL DEFAULT false,
    commodity_title text NULL,
    commodity_code varchar(8) NULL,
    class_title text NULL,
    class_code varchar(8) NULL,
    family_title text NULL,
    family_code varchar(8) NULL,
    segment_title text NOT NULL,
    segment_code varchar(8) NOT NULL,
    synonyms text[] NOT NULL DEFAULT '{}',
    examples text[] NOT NULL DEFAULT '{}',
    search_document text NOT NULL,
    embedding_text text NOT NULL,
    embedding vector(3072) NULL,
    embedding_model varchar(64) NOT NULL,
    embedding_version integer NOT NULL DEFAULT 1,
    metadata jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lip_v2_unspsc_embeddings_identity UNIQUE (
        unspsc_release_version,
        level,
        COALESCE(segment_code, ''),
        COALESCE(family_code, ''),
        COALESCE(class_code, ''),
        COALESCE(commodity_code, '')
    ),
    CONSTRAINT chk_lip_v2_unspsc_level
        CHECK (level IN ('SEGMENT', 'FAMILY', 'CLASS', 'COMMODITY')),
    CONSTRAINT chk_lip_v2_unspsc_leaf_consistency
        CHECK (
            (is_leaf = true AND commodity_code IS NOT NULL)
            OR
            (is_leaf = false)
        )
);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_release_level
    ON lip_v2_unspsc_embeddings_v2 (unspsc_release_version, level);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_segment
    ON lip_v2_unspsc_embeddings_v2 (segment_code);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_family
    ON lip_v2_unspsc_embeddings_v2 (family_code);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_class
    ON lip_v2_unspsc_embeddings_v2 (class_code);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_commodity
    ON lip_v2_unspsc_embeddings_v2 (commodity_code);

CREATE INDEX IF NOT EXISTS idx_lip_v2_unspsc_embeddings_search_document_trgm
    ON lip_v2_unspsc_embeddings_v2
    USING gin (search_document gin_trgm_ops);
