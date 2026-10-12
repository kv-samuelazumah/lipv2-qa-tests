from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import boto3
from pydantic import ValidationError

from ..core.config import Config
from ..pipeline.models import LineItemPipelineInput, LineItemPipelineResult
from ..pipeline.service import LineItemPipelineService
from .schemas import (
    FailureReason,
    LineItemProcessingCompleted,
    LineItemProcessingFailed,
    LineItemProcessingRequested,
)


LOG = logging.getLogger("lip.v2.worker")

CONFIDENCE_SCORES: Dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}


class LineItemWorker:
    def __init__(self, pipeline: Optional[LineItemPipelineService] = None) -> None:
        self.input_queue_url = self._required_env("LINE_ITEM_INPUT_QUEUE_URL")
        self.result_queue_url = (
            os.getenv("DOCUMENT_METADATA_SQS_URL")
            or os.getenv("OCR_STATUS_QUEUE_URL")
            or os.getenv("LINE_ITEM_RESULT_QUEUE_URL")
        )
        if not self.result_queue_url:
            raise ValueError(
                "Missing required environment variable: DOCUMENT_METADATA_SQS_URL, "
                "OCR_STATUS_QUEUE_URL, or LINE_ITEM_RESULT_QUEUE_URL"
            )
        self.post_ocr_queue_url = self._required_env("POST_OCR_QUEUE_URL")
        self.dlq_url = os.getenv("LINE_ITEM_DLQ_URL")
        self.wait_time_seconds = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
        self.visibility_timeout = int(os.getenv("SQS_VISIBILITY_TIMEOUT_SECONDS", "120"))
        self.worker_enabled = os.getenv("WORKER_ENABLED", "true").lower() == "true"
        self.idle_sleep_seconds = int(os.getenv("WORKER_IDLE_SLEEP_SECONDS", "30"))
        self.log_line_items = os.getenv("LOG_LINE_ITEMS", "true").lower() == "true"
        self.line_item_preview_chars = int(os.getenv("LINE_ITEM_PREVIEW_CHARS", "200"))

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=log_level)

        endpoint_url = os.getenv("AWS_ENDPOINT_URL") or self._derive_endpoint_from_queue_url(
            self.input_queue_url
        )
        self.sqs = boto3.client(
            "sqs",
            region_name=os.getenv("AWS_REGION"),
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )
        self._ensure_localstack_queues(endpoint_url)
        self.pipeline = pipeline or LineItemPipelineService()

    @staticmethod
    def _required_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise ValueError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _derive_endpoint_from_queue_url(queue_url: str) -> Optional[str]:
        parsed = urlparse(queue_url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _extract_queue_name(queue_url: str) -> Optional[str]:
        parsed = urlparse(queue_url)
        if not parsed.path:
            return None
        parts = [segment for segment in parsed.path.split("/") if segment]
        if not parts:
            return None
        return parts[-1]

    def _ensure_localstack_queues(self, endpoint_url: Optional[str]) -> None:
        if not endpoint_url:
            return
        endpoint = endpoint_url.lower()
        if "localhost" not in endpoint and "localstack" not in endpoint:
            return

        queue_urls = [self.input_queue_url, self.result_queue_url]
        if self.post_ocr_queue_url:
            queue_urls.append(self.post_ocr_queue_url)
        if self.dlq_url:
            queue_urls.append(self.dlq_url)

        created: list[str] = []
        for queue_url in queue_urls:
            queue_name = self._extract_queue_name(queue_url)
            if not queue_name:
                continue
            attrs = None
            if queue_name.endswith(".fifo"):
                attrs = {"FifoQueue": "true", "ContentBasedDeduplication": "true"}
            self.sqs.create_queue(QueueName=queue_name, Attributes=attrs or {})
            created.append(queue_name)
        if created:
            LOG.info("LocalStack queues ensured: %s", ", ".join(created))

    def run_forever(self) -> None:
        LOG.info(
            "Starting 13-lip-v2 worker loop input_queue=%s result_queue=%s post_ocr_queue=%s "
            "visibility_timeout_seconds=%s",
            self._extract_queue_name(self.input_queue_url),
            self._extract_queue_name(self.result_queue_url),
            self._extract_queue_name(self.post_ocr_queue_url),
            self.visibility_timeout,
        )
        while self.worker_enabled:
            if not self.input_queue_url or self.sqs is None:
                LOG.warning(
                    "Worker is running without LINE_ITEM_INPUT_QUEUE_URL; idling until configuration is provided"
                )
                time.sleep(self.idle_sleep_seconds)
                continue
            response = self.sqs.receive_message(
                QueueUrl=self.input_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=self.wait_time_seconds,
                VisibilityTimeout=self.visibility_timeout,
            )
            for message in response.get("Messages", []):
                self._handle_message(message)

    def _handle_message(self, sqs_message: Dict[str, Any]) -> None:
        receipt_handle = sqs_message["ReceiptHandle"]
        raw_body = sqs_message.get("Body", "{}")
        message_id = sqs_message.get("MessageId")

        LOG.info("Line item message received message_id=%s", message_id)

        try:
            body = json.loads(raw_body)
            payload = self._unwrap_sns_envelope(body)
            request = LineItemProcessingRequested.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            LOG.exception(
                "Invalid inbound message; parking or dropping message_id=%s",
                message_id,
            )
            self._park_invalid_message(raw_body, str(exc))
            self._delete_message(receipt_handle)
            return

        try:
            started_at = time.perf_counter()
            if self.log_line_items:
                LOG.info(
                    "Classification started org=%s tx=%s index=%s correlation_id=%s "
                    "supplier=%r line_item=%r",
                    request.orgId,
                    request.transactionId,
                    request.lineItemIndex,
                    request.correlationId,
                    self._preview_text(request.supplierRaw or ""),
                    self._preview_text(request.lineItemText),
                )
            else:
                LOG.info(
                    "Classification started org=%s tx=%s index=%s correlation_id=%s",
                    request.orgId,
                    request.transactionId,
                    request.lineItemIndex,
                    request.correlationId,
                )

            result = self.pipeline.process(
                LineItemPipelineInput(
                    org_id=str(request.orgId),
                    supplier_raw=request.supplierRaw or "",
                    line_item_raw=request.lineItemText,
                )
            )
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._log_pipeline_result(request, result, elapsed_ms)
            completed = self._to_completed_event(request, result)
            self._publish_result_event(completed)
            LOG.info(
                "Result event published org=%s tx=%s index=%s event_id=%s queue=%s",
                request.orgId,
                request.transactionId,
                request.lineItemIndex,
                completed.eventId,
                self._extract_queue_name(self.result_queue_url),
            )
            self._publish_post_ocr_event(request, completed)
            LOG.info(
                "Post-OCR event published org=%s tx=%s index=%s queue=%s",
                request.orgId,
                request.transactionId,
                request.lineItemIndex,
                self._extract_queue_name(self.post_ocr_queue_url),
            )
            self._delete_message(receipt_handle)
            LOG.info(
                "Processed org=%s tx=%s index=%s correlation_id=%s solved_by=%s "
                "category_code=%s category_tier=%s elapsed_ms=%.1f",
                request.orgId,
                request.transactionId,
                request.lineItemIndex,
                request.correlationId,
                completed.solvedBy,
                completed.categoryCode,
                completed.categoryTier,
                elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001
            LOG.exception(
                "Failed processing message; leaving message for retry org=%s tx=%s "
                "index=%s correlation_id=%s message_id=%s",
                request.orgId,
                request.transactionId,
                request.lineItemIndex,
                request.correlationId,
                message_id,
            )
            self._publish_failure_event(request, str(exc))

    def _log_pipeline_result(
        self,
        request: LineItemProcessingRequested,
        result: LineItemPipelineResult,
        elapsed_ms: float,
    ) -> None:
        final = result.final_result or {}
        retrieval = result.retrieval_result or {}
        retrieval_metadata = retrieval.get("retrieval_metadata") or {}
        evaluation = result.evaluation_result or {}
        identify = result.identify_search_result or {}

        LOG.info(
            "Classification execution org=%s tx=%s index=%s stage=%s resolved_by=%s "
            "status_code=%s query_count=%s candidate_count=%s evaluation_decision=%s "
            "category_code=%s category_tier=%s elapsed_ms=%.1f",
            request.orgId,
            request.transactionId,
            request.lineItemIndex,
            result.stage,
            final.get("resolved_by"),
            final.get("status_code"),
            len(identify.get("unspsc_search_queries") or []),
            retrieval_metadata.get("candidate_count", len(retrieval.get("candidates") or [])),
            evaluation.get("decision"),
            final.get("unspsc_code"),
            final.get("unspsc_level"),
            elapsed_ms,
        )

    def _preview_text(self, value: str) -> str:
        compact = " ".join(value.split())
        if len(compact) <= self.line_item_preview_chars:
            return compact
        return f"{compact[: self.line_item_preview_chars]}..."

    @staticmethod
    def _unwrap_sns_envelope(body: Dict[str, Any]) -> Dict[str, Any]:
        if body.get("Type") == "Notification" and isinstance(body.get("Message"), str):
            return json.loads(body["Message"])
        return body

    def _to_completed_event(
        self,
        request: LineItemProcessingRequested,
        result: LineItemPipelineResult,
    ) -> LineItemProcessingCompleted:
        final_result = result.final_result or {}
        category_code = final_result.get("unspsc_code")
        taxonomy_version = self._taxonomy_version(result)
        if not category_code:
            return LineItemProcessingCompleted(
                orgId=request.orgId,
                transactionId=request.transactionId,
                uploadedDocumentId=request.uploadedDocumentId,
                lineItemIndex=request.lineItemIndex,
                lineItemText=request.lineItemText,
                solvedBy="FAILED",
                categoryCode=None,
                categoryTitle=None,
                categoryTier=None,
                confidence=self._confidence(result),
                taxonomyVersion=taxonomy_version,
                reasoning=result.as_dict(),
                correlationId=request.correlationId,
                classificationContext=request.classificationContext,
            )

        return LineItemProcessingCompleted(
            orgId=request.orgId,
            transactionId=request.transactionId,
            uploadedDocumentId=request.uploadedDocumentId,
            lineItemIndex=request.lineItemIndex,
            lineItemText=request.lineItemText,
            # Keep the existing cross-service event contract. The exact v2
            # resolution path remains available in reasoning.final_result.resolved_by.
            solvedBy="OPENAI",
            categoryCode=category_code,
            categoryTitle=final_result.get("selected_label"),
            categoryTier=final_result.get("unspsc_level"),
            confidence=self._confidence(result),
            taxonomyVersion=taxonomy_version,
            reasoning=result.as_dict(),
            correlationId=request.correlationId,
            classificationContext=request.classificationContext,
        )

    @staticmethod
    def _confidence(result: LineItemPipelineResult) -> Optional[float]:
        final_classification = (result.evaluation_result or {}).get("final_classification") or {}
        return CONFIDENCE_SCORES.get(final_classification.get("classification_confidence"))

    @staticmethod
    def _taxonomy_version(result: LineItemPipelineResult) -> Optional[str]:
        version = (result.retrieval_result or {}).get("unspsc_version") or Config.get_unspsc_version()
        return None if version in (None, "", "unknown") else version

    def _publish_result_event(self, event: LineItemProcessingCompleted) -> None:
        params: Dict[str, Any] = dict(
            QueueUrl=self.result_queue_url,
            MessageBody=event.model_dump_json(),
        )
        if self.result_queue_url.endswith(".fifo"):
            params["MessageGroupId"] = f"{event.orgId}:{event.transactionId}"
            params["MessageDeduplicationId"] = (
                f"{event.orgId}:{event.transactionId}:{event.lineItemIndex}:{event.solvedBy}"
            )
        self.sqs.send_message(**params)

    def _publish_post_ocr_event(
        self,
        request: LineItemProcessingRequested,
        completed: LineItemProcessingCompleted,
    ) -> None:
        if request.uploadedDocumentId is None:
            raise ValueError("uploadedDocumentId is required to trigger post-ocr processing")
        body = {
            "schemaVersion": 1,
            "eventType": "LineItemProcessingCompleted",
            "orgId": str(request.orgId),
            "transactionId": str(request.transactionId),
            "uploadedDocumentId": str(request.uploadedDocumentId) if request.uploadedDocumentId else None,
            "lineItemIndex": request.lineItemIndex,
            "lineItemText": request.lineItemText,
            "categoryCode": completed.categoryCode,
            "categoryTier": completed.categoryTier,
            "correlationId": request.correlationId,
        }
        params: Dict[str, Any] = dict(
            QueueUrl=self.post_ocr_queue_url,
            MessageBody=json.dumps(body),
        )
        if self.post_ocr_queue_url.endswith(".fifo"):
            params["MessageGroupId"] = f"{request.orgId}:{request.transactionId}"
            params["MessageDeduplicationId"] = (
                f"{request.orgId}:{request.transactionId}:{request.lineItemIndex}:post-ocr"
            )
        self.sqs.send_message(**params)

    def _publish_failure_event(self, request: LineItemProcessingRequested, message: str) -> None:
        if not self.result_queue_url or self.sqs is None:
            LOG.warning("Skipping failure publish because no result queue is configured")
            return
        event = LineItemProcessingFailed(
            orgId=request.orgId,
            transactionId=request.transactionId,
            uploadedDocumentId=request.uploadedDocumentId,
            lineItemIndex=request.lineItemIndex,
            correlationId=request.correlationId,
            reason=FailureReason(code="WORKER_ERROR", message=message),
        )
        params: Dict[str, Any] = dict(
            QueueUrl=self.result_queue_url,
            MessageBody=event.model_dump_json(),
        )
        if self.result_queue_url.endswith(".fifo"):
            params["MessageGroupId"] = f"{request.orgId}:{request.transactionId}"
            params["MessageDeduplicationId"] = (
                f"{request.orgId}:{request.transactionId}:{request.lineItemIndex}:failed"
            )
        self.sqs.send_message(**params)

    def _park_invalid_message(self, raw_body: str, error_message: str) -> None:
        if not self.dlq_url or self.sqs is None:
            return
        params: Dict[str, Any] = dict(
            QueueUrl=self.dlq_url,
            MessageBody=json.dumps({"body": raw_body, "error": error_message}),
        )
        if self.dlq_url.endswith(".fifo"):
            params["MessageGroupId"] = "invalid-line-item-events"
            params["MessageDeduplicationId"] = hashlib.sha256(raw_body.encode()).hexdigest()
        self.sqs.send_message(**params)

    def _delete_message(self, receipt_handle: str) -> None:
        if not self.input_queue_url or self.sqs is None:
            return
        self.sqs.delete_message(QueueUrl=self.input_queue_url, ReceiptHandle=receipt_handle)

    def close(self) -> None:
        close = getattr(self.pipeline, "close", None)
        if callable(close):
            close()
