from __future__ import annotations

from typing import Any, List, Protocol

from ..core.config import Config


class EmbeddingClient(Protocol):
    def embed_query(self, text: str) -> List[float]:
        ...

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...


class OpenAIEmbeddingClient:
    def __init__(self):
        self.api_key = Config.get_openai_embedding_api_key()
        self.model = Config.get_openai_embedding_model()
        self.base_url = Config.get_openai_embedding_base_url()
        self._client: Any = None

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for semantic search embeddings")
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for OpenAIEmbeddingClient") from exc

        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = self._client.embeddings.create(model=self.model, input=texts)
        return [list(item.embedding) for item in response.data]
