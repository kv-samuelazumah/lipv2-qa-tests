from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LineItemProcessingRequested(BaseModel):
    schemaVersion: Literal[1]
    eventId: UUID
    eventType: Literal["LineItemProcessingRequested"]
    occurredAt: datetime
    orgId: UUID
    transactionId: UUID
    uploadedDocumentId: Optional[UUID] = None
    lineItemIndex: int = Field(ge=0)
    lineItemText: str = Field(min_length=1)
    supplierRaw: Optional[str] = None
    correlationId: Optional[str] = None
    classificationContext: Optional[Dict[str, Any]] = None


class LineItemProcessingCompleted(BaseModel):
    schemaVersion: Literal[1] = 1
    eventId: UUID = Field(default_factory=uuid4)
    eventType: Literal["LineItemProcessingCompleted"] = "LineItemProcessingCompleted"
    occurredAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    orgId: UUID
    transactionId: UUID
    uploadedDocumentId: Optional[UUID] = None
    lineItemIndex: int = Field(ge=0)
    lineItemText: str = Field(min_length=1)
    solvedBy: Literal["OPENAI", "FAILED"]
    categoryCode: Optional[str] = None
    categoryTitle: Optional[str] = None
    categoryTier: Optional[str] = None
    confidence: Optional[float] = None
    taxonomyVersion: Optional[str] = None
    reasoning: Optional[Dict[str, Any]] = None
    correlationId: Optional[str] = None
    classificationContext: Optional[Dict[str, Any]] = None


class FailureReason(BaseModel):
    code: str
    message: str


class LineItemProcessingFailed(BaseModel):
    schemaVersion: Literal[1] = 1
    eventId: UUID = Field(default_factory=uuid4)
    eventType: Literal["LineItemProcessingFailed"] = "LineItemProcessingFailed"
    occurredAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    orgId: UUID
    transactionId: UUID
    uploadedDocumentId: Optional[UUID] = None
    lineItemIndex: int = Field(ge=0)
    correlationId: Optional[str] = None
    reason: FailureReason
