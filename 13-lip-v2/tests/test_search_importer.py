import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.search.importer import (
    UnspscCorpusImporter,
    _summarize_bulk_errors,
    build_index_document,
    count_corpus_jsonl,
    iter_corpus_batches,
    read_corpus_jsonl,
)


SAMPLE_RECORD = {
    "nodeKey": "commodity:10101501",
    "code": "10101501",
    "tier": "Commodity",
    "depth": 4,
    "title": "Cats",
    "parentCode": "10101500",
    "segmentCode": "10000000",
    "familyCode": "10100000",
    "classCode": "10101500",
    "commodityCode": "10101501",
    "segmentTitle": "Live Plant and Animal Material and Accessories and Supplies",
    "familyTitle": "Live animals",
    "classTitle": "Livestock",
    "commodityTitle": "Cats",
    "pathCodes": ["10000000", "10100000", "10101500", "10101501"],
    "pathTitles": [
        "Live Plant and Animal Material and Accessories and Supplies",
        "Live animals",
        "Livestock",
        "Cats",
    ],
    "breadcrumbText": "Live Plant and Animal Material and Accessories and Supplies > Live animals > Livestock > Cats",
    "searchableText": "Commodity | Cats | 10101501",
    "embeddingText": "UNSPSC Commodity 10101501: Cats.",
    "source": "UNSPSC English v260801.1",
    "selectable": True,
}


class FakeEmbeddingClient:
    def __init__(self):
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(index + 1)] * 3 for index, _ in enumerate(texts)]


class FakeIndexBackend:
    def __init__(self):
        self.ensure_index_calls = 0
        self.ensure_index_dims = []
        self.bulk_calls = []

    def ensure_index(self, embedding_dimensions):
        self.ensure_index_calls += 1
        self.ensure_index_dims.append(embedding_dimensions)

    def bulk_index(self, documents):
        self.bulk_calls.append(documents)


class SearchImporterTests(unittest.TestCase):
    def test_read_corpus_jsonl_reads_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.jsonl"
            path.write_text(json.dumps(SAMPLE_RECORD) + "\n", encoding="utf-8")

            records = list(read_corpus_jsonl(str(path)))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].node_key, "commodity:10101501")
        self.assertEqual(records[0].embedding_text, "UNSPSC Commodity 10101501: Cats.")

    def test_count_and_batch_iteration_work_for_streaming_import(self):
        second = dict(SAMPLE_RECORD)
        second["nodeKey"] = "commodity:10101502"
        second["code"] = "10101502"
        second["commodityCode"] = "10101502"
        second["commodityTitle"] = "Dogs"
        second["title"] = "Dogs"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.jsonl"
            path.write_text(
                "\n".join([json.dumps(SAMPLE_RECORD), json.dumps(second)]) + "\n",
                encoding="utf-8",
            )

            count = count_corpus_jsonl(str(path))
            batches = list(iter_corpus_batches(str(path), 1))

        self.assertEqual(count, 2)
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0][0].code, "10101501")
        self.assertEqual(batches[1][0].code, "10101502")

    def test_build_index_document_maps_expected_fields(self):
        record = next(read_corpus_jsonl_from_lines([json.dumps(SAMPLE_RECORD)]))

        document = build_index_document(record=record, embedding=[0.1, 0.2, 0.3])

        self.assertEqual(document["node_key"], "commodity:10101501")
        self.assertEqual(document["level"], "COMMODITY")
        self.assertEqual(document["search_document"], "Commodity | Cats | 10101501")
        self.assertEqual(document["embedding"], [0.1, 0.2, 0.3])

    def test_importer_batches_embeddings_and_bulk_indexing(self):
        second = dict(SAMPLE_RECORD)
        second["nodeKey"] = "commodity:10101502"
        second["code"] = "10101502"
        second["commodityCode"] = "10101502"
        second["commodityTitle"] = "Dogs"
        second["title"] = "Dogs"
        second["embeddingText"] = "UNSPSC Commodity 10101502: Dogs."
        second["searchableText"] = "Commodity | Dogs | 10101502"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corpus.jsonl"
            path.write_text(
                "\n".join([json.dumps(SAMPLE_RECORD), json.dumps(second)]) + "\n",
                encoding="utf-8",
            )
            embedding_client = FakeEmbeddingClient()
            index_backend = FakeIndexBackend()
            progress_messages = []
            importer = UnspscCorpusImporter(
                embedding_client=embedding_client,
                index_backend=index_backend,
                batch_size=1,
                progress_callback=progress_messages.append,
            )

            imported = importer.import_file(str(path))

        self.assertEqual(imported, 2)
        self.assertEqual(index_backend.ensure_index_calls, 1)
        self.assertEqual(index_backend.ensure_index_dims, [3])
        self.assertEqual(len(embedding_client.calls), 2)
        self.assertEqual(len(index_backend.bulk_calls), 2)
        self.assertEqual(index_backend.bulk_calls[0][0]["code"], "10101501")
        self.assertEqual(index_backend.bulk_calls[1][0]["code"], "10101502")
        self.assertTrue(any("batch 1/2" in message for message in progress_messages))
        self.assertTrue(any("completed indexing 2 records" in message for message in progress_messages))

    def test_bulk_error_summary_includes_document_reason(self):
        summary = _summarize_bulk_errors(
            {
                "errors": True,
                "items": [
                    {
                        "index": {
                            "_id": "commodity:10101501",
                            "error": {
                                "type": "mapper_parsing_exception",
                                "reason": "failed to parse field [embedding]",
                                "caused_by": {"reason": "dimension mismatch"},
                            },
                        }
                    }
                ],
            }
        )

        self.assertIn("commodity:10101501", summary)
        self.assertIn("mapper_parsing_exception", summary)
        self.assertIn("dimension mismatch", summary)


def read_corpus_jsonl_from_lines(lines):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "corpus.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        yield from read_corpus_jsonl(str(path))


if __name__ == "__main__":
    unittest.main()
