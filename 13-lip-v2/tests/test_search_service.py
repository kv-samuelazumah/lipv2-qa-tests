import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.identify_search.models import QueryType, UnspscSearchQuery
from app.search.embedding_client import OpenAIEmbeddingClient
from app.search.models import UnspscSearchToolRequest
from app.search.service import UnspscSearchTool


class RecordingEmbeddingClient:
    def __init__(self):
        self.batches = []

    def embed_query(self, text):
        raise AssertionError("search should use the batched embedding API")

    def embed_texts(self, texts):
        self.batches.append(list(texts))
        return [[float(index)] for index, _ in enumerate(texts)]


class RecordingSearchBackend:
    def __init__(self):
        self.semantic_vectors = []

    def exact_search(self, query, limit):
        return []

    def bm25_search(self, query, limit):
        return []

    def semantic_search(self, query, vector, limit):
        self.semantic_vectors.append((query.query, vector))
        return []


class UnspscSearchToolTests(unittest.TestCase):
    def test_all_query_embeddings_are_requested_in_one_batch(self):
        embeddings = RecordingEmbeddingClient()
        backend = RecordingSearchBackend()
        tool = UnspscSearchTool(
            search_backend=backend,
            embedding_client=embeddings,
        )

        tool.run(
            UnspscSearchToolRequest(
                queries=[
                    UnspscSearchQuery(
                        query="protective clothing",
                        query_type=QueryType.BROAD,
                        priority=2,
                        reason="fallback",
                    ),
                    UnspscSearchQuery(
                        query="disposable paper coveralls",
                        query_type=QueryType.SPECIFIC,
                        priority=1,
                        reason="primary identity",
                    ),
                ],
                max_candidates_per_query=10,
                max_candidates_total=30,
            )
        )

        self.assertEqual(
            embeddings.batches,
            [["disposable paper coveralls", "protective clothing"]],
        )
        self.assertEqual(
            backend.semantic_vectors,
            [
                ("disposable paper coveralls", [0.0]),
                ("protective clothing", [1.0]),
            ],
        )

    def test_openai_embedding_client_reuses_sdk_client(self):
        sdk_client = MagicMock()
        sdk_client.embeddings.create.side_effect = [
            SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])]),
            SimpleNamespace(data=[SimpleNamespace(embedding=[2.0])]),
        ]

        with patch("openai.OpenAI", return_value=sdk_client) as client_factory:
            client = OpenAIEmbeddingClient()
            client.api_key = "test-key"
            self.assertEqual(client.embed_texts(["first"]), [[1.0]])
            self.assertEqual(client.embed_texts(["second"]), [[2.0]])

        client_factory.assert_called_once()


if __name__ == "__main__":
    unittest.main()
