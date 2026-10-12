from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional, Protocol

from ..core.config import Config
from .embedding_client import EmbeddingClient, OpenAIEmbeddingClient
from .elasticsearch_client import ElasticsearchUnspscSearchBackend


@dataclass(frozen=True)
class UnspscCorpusRecord:
    node_key: str
    code: str
    tier: str
    depth: int
    title: str
    parent_code: Optional[str]
    segment_code: str
    family_code: Optional[str]
    class_code: Optional[str]
    commodity_code: Optional[str]
    segment_title: str
    family_title: Optional[str]
    class_title: Optional[str]
    commodity_title: Optional[str]
    path_codes: List[str]
    path_titles: List[str]
    breadcrumb_text: str
    searchable_text: str
    embedding_text: str
    source: str
    selectable: bool

    @classmethod
    def from_dict(cls, data: dict) -> "UnspscCorpusRecord":
        return cls(
            node_key=str(data["nodeKey"]),
            code=str(data["code"]),
            tier=str(data["tier"]),
            depth=int(data["depth"]),
            title=str(data["title"]),
            parent_code=data.get("parentCode"),
            segment_code=str(data["segmentCode"]),
            family_code=data.get("familyCode"),
            class_code=data.get("classCode"),
            commodity_code=data.get("commodityCode"),
            segment_title=str(data["segmentTitle"]),
            family_title=data.get("familyTitle"),
            class_title=data.get("classTitle"),
            commodity_title=data.get("commodityTitle"),
            path_codes=[str(value) for value in data.get("pathCodes", [])],
            path_titles=[str(value) for value in data.get("pathTitles", [])],
            breadcrumb_text=str(data["breadcrumbText"]),
            searchable_text=str(data["searchableText"]),
            embedding_text=str(data["embeddingText"]),
            source=str(data["source"]),
            selectable=bool(data["selectable"]),
        )


class UnspscIndexBackend(Protocol):
    def ensure_index(self, embedding_dimensions: int) -> None:
        ...

    def bulk_index(self, documents: List[dict]) -> None:
        ...


class ElasticsearchUnspscIndexBackend:
    def __init__(self):
        self.search_backend = ElasticsearchUnspscSearchBackend()
        self.base_url = self.search_backend.base_url
        self.index_name = self.search_backend.index_name
        self.api_key = self.search_backend.api_key
        self.username = self.search_backend.username
        self.password = self.search_backend.password

    def ensure_index(self, embedding_dimensions: int) -> None:
        from urllib import request
        import base64

        body = {
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                }
            },
            "mappings": {
                "properties": {
                    "node_key": {"type": "keyword"},
                    "code": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "tier": {"type": "keyword"},
                    "depth": {"type": "integer"},
                    "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "parent_code": {"type": "keyword"},
                    "segment_code": {"type": "keyword"},
                    "family_code": {"type": "keyword"},
                    "class_code": {"type": "keyword"},
                    "commodity_code": {"type": "keyword"},
                    "segment_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "family_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "class_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "commodity_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "path": {"type": "text"},
                    "path_codes": {"type": "keyword"},
                    "path_titles": {"type": "text"},
                    "breadcrumb_text": {"type": "text"},
                    "search_document": {"type": "text"},
                    "embedding_text": {"type": "text"},
                    "synonyms": {"type": "keyword"},
                    "examples": {"type": "keyword"},
                    "code_aliases": {"type": "keyword"},
                    "specific_rules": {
                        "type": "nested",
                        "properties": {
                            "rule_id": {"type": "keyword"},
                            "applies_to_code": {"type": "keyword"},
                            "applies_to_label": {"type": "keyword"},
                            "applies_to_level": {"type": "keyword"},
                            "rule_scope": {"type": "keyword"},
                            "rule_text": {"type": "text"},
                        },
                    },
                    "source": {"type": "keyword"},
                    "selectable": {"type": "boolean"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": embedding_dimensions,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {token}"
        req = request.Request(
            url=f"{self.base_url}/{self.index_name}",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="PUT",
        )
        try:
            with request.urlopen(req):  # noqa: S310
                return
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            message = str(exc)
            if "resource_already_exists_exception" in message or "400" in message:
                self._validate_existing_index_dimensions(embedding_dimensions)
                return
            raise

    def _validate_existing_index_dimensions(self, embedding_dimensions: int) -> None:
        from urllib import request
        import base64

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {token}"
        req = request.Request(
            url=f"{self.base_url}/{self.index_name}/_mapping",
            headers=headers,
            method="GET",
        )
        with request.urlopen(req) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
        properties = body.get(self.index_name, {}).get("mappings", {}).get("properties", {})
        actual_dims = properties.get("embedding", {}).get("dims")
        if actual_dims is None:
            return
        if int(actual_dims) != int(embedding_dimensions):
            raise RuntimeError(
                f"existing index '{self.index_name}' has embedding dims={actual_dims}, "
                f"but current embedding model returns dims={embedding_dimensions}. "
                f"Delete the index and re-run the import, or use a different ELASTICSEARCH_UNSPSC_INDEX."
            )

    def bulk_index(self, documents: List[dict]) -> None:
        if not documents:
            return
        from urllib import request
        import base64

        lines: List[str] = []
        for doc in documents:
            doc_id = str(doc["node_key"])
            lines.append(json.dumps({"index": {"_index": self.index_name, "_id": doc_id}}))
            lines.append(json.dumps(doc))
        payload = "\n".join(lines) + "\n"
        headers = {"Content-Type": "application/x-ndjson"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {token}"
        req = request.Request(
            url=f"{self.base_url}/_bulk",
            data=payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("errors"):
            raise RuntimeError(_summarize_bulk_errors(body))


class UnspscCorpusImporter:
    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        index_backend: Optional[UnspscIndexBackend] = None,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.embedding_client = embedding_client or OpenAIEmbeddingClient()
        self.index_backend = index_backend or ElasticsearchUnspscIndexBackend()
        self.batch_size = batch_size or Config.get_unspsc_import_batch_size()
        self.progress_callback = progress_callback or _default_progress_callback

    def import_file(self, path: str) -> int:
        total_records = count_corpus_jsonl(path)
        embedding_model = getattr(self.embedding_client, "model", "unknown")
        self.progress_callback(
            f"[unspsc-import] preparing index for {total_records} records from {path}"
        )
        self.progress_callback(
            f"[unspsc-import] embedding model configured: {embedding_model}"
        )
        self.progress_callback("[unspsc-import] starting embedding and bulk indexing")
        total = 0
        total_batches = ((total_records - 1) // self.batch_size) + 1 if total_records > 0 else 0
        index_ready = False
        for batch_number, batch in enumerate(iter_corpus_batches(path, self.batch_size), start=1):
            embeddings = self.embedding_client.embed_texts([record.embedding_text for record in batch])
            if not index_ready:
                embedding_dimensions = len(embeddings[0]) if embeddings else 0
                if embedding_dimensions <= 0:
                    raise RuntimeError("embedding client returned an empty vector")
                self.index_backend.ensure_index(embedding_dimensions)
                self.progress_callback(
                    f"[unspsc-import] index ready with embedding dims={embedding_dimensions}"
                )
                index_ready = True
            docs = [
                build_index_document(record=record, embedding=embedding)
                for record, embedding in zip(batch, embeddings, strict=True)
            ]
            try:
                self.index_backend.bulk_index(docs)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"bulk index failed on batch {batch_number}/{total_batches} "
                    f"after indexing {total}/{total_records} records: {exc}"
                ) from exc
            total += len(docs)
            percentage = 100.0 if total_records == 0 else (total / total_records) * 100.0
            self.progress_callback(
                f"[unspsc-import] batch {batch_number}/{total_batches} indexed "
                f"{total}/{total_records} records ({percentage:.1f}%)"
            )
        self.progress_callback(f"[unspsc-import] completed indexing {total} records")
        return total


def read_corpus_jsonl(path: str) -> Iterable[UnspscCorpusRecord]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            yield UnspscCorpusRecord.from_dict(json.loads(stripped))


def count_corpus_jsonl(path: str) -> int:
    file_path = Path(path)
    count = 0
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def iter_corpus_batches(path: str, batch_size: int) -> Iterator[List[UnspscCorpusRecord]]:
    batch: List[UnspscCorpusRecord] = []
    for record in read_corpus_jsonl(path):
        batch.append(record)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_index_document(*, record: UnspscCorpusRecord, embedding: List[float]) -> dict:
    level = record.tier.upper()
    return {
        "node_key": record.node_key,
        "code": record.code,
        "level": level,
        "tier": record.tier,
        "depth": record.depth,
        "title": record.title,
        "parent_code": record.parent_code,
        "segment_code": record.segment_code,
        "family_code": record.family_code,
        "class_code": record.class_code,
        "commodity_code": record.commodity_code,
        "segment_title": record.segment_title,
        "family_title": record.family_title,
        "class_title": record.class_title,
        "commodity_title": record.commodity_title,
        "path": record.breadcrumb_text,
        "path_codes": record.path_codes,
        "path_titles": record.path_titles,
        "breadcrumb_text": record.breadcrumb_text,
        "search_document": record.searchable_text,
        "embedding_text": record.embedding_text,
        "synonyms": [],
        "examples": [],
        "code_aliases": [],
        "specific_rules": [],
        "source": record.source,
        "selectable": record.selectable,
        "embedding": embedding,
    }


def _summarize_bulk_errors(body: dict) -> str:
    failures: List[str] = []
    for item in body.get("items", []):
        action = item.get("index") or item.get("create") or item.get("update") or item.get("delete")
        if not isinstance(action, dict):
            continue
        error = action.get("error")
        if not error:
            continue
        doc_id = action.get("_id", "<unknown>")
        error_type = error.get("type", "unknown_error")
        reason = error.get("reason", str(error))
        caused_by = error.get("caused_by") or {}
        caused_reason = caused_by.get("reason")
        if caused_reason:
            failures.append(f"id={doc_id} type={error_type} reason={reason}; caused_by={caused_reason}")
        else:
            failures.append(f"id={doc_id} type={error_type} reason={reason}")
        if len(failures) >= 3:
            break
    if not failures:
        return "Elasticsearch bulk index reported errors, but no item-level details were returned"
    return "Elasticsearch bulk index reported errors: " + " | ".join(failures)


def _default_progress_callback(message: str) -> None:
    print(message, flush=True)
