from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    PROVEN = "proven"
    PARTIALLY_PROVEN = "partially_proven"
    NOT_PROVEN = "not_proven"
    UNVERIFIABLE = "unverifiable"


class LemmaStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="What automation was supposed to do")
    claim: str = Field(..., min_length=1, description="What said automation claims it completed")
    evidence: str = Field(..., min_length=1, description="Logs, files, screenshots, outputs, etc.")


class RecheckRequest(BaseModel):
    new_evidence: str = Field(..., min_length=1, description="Addl. proof collected after the fix thing")


class LemmaCheck(BaseModel):
    claim: str
    status: LemmaStatus
    evidence: str
    missing_proof: Optional[str] = None


class Risk(BaseModel):
    label: str
    severity: Severity
    description: str


class VerificationReportResponse(BaseModel):
    id: str
    goal: str
    claim: str
    evidence: str
    verdict: Verdict
    confidence: int = Field(..., ge=0, le=100)
    summary: str
    lemmas: List[LemmaCheck]
    missing_proof: List[str]
    risks: List[Risk]
    fix_instruction: str
    created_at: datetime
    updated_at: datetime
