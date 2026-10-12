# 13-lip-v2 SQL

`001_pre_agentic_tables.sql` creates new `13-lip-v2` tables without mutating
the old `06-line-item-processor` tables.

## Tables

- `lip_v2_line_item_solution`
  - pre-agentic reuse cache keyed by `lookup_hash`
  - `stable` is constrained against `solved_for`

- `lip_v2_non_unspsc_rules`
  - ordered, data-driven regex/policy rules
  - first active matching rule wins

- `lip_v2_unspsc_embeddings_v2`
  - richer UNSPSC retrieval table
  - keeps the old `unspsc_embeddings` table untouched

## Notes

- This DDL assumes the same Postgres infrastructure used by
  `06-line-item-processor`.
- `vector` and `pg_trgm` extensions are enabled here because the new embeddings
  table supports both vector and lexical retrieval.
- `embedding` is declared as `vector(3072)` for `text-embedding-3-large`.
  If you switch models, change the dimension before loading data.
- pgvector approximate indexes are not created for 3072-dimensional embeddings
  in this setup.
- if you want ANN indexing later, switch to a smaller embedding dimension or a
  different storage/indexing strategy.
