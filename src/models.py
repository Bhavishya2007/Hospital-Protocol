"""Pydantic data models for Hospital Protocol Authoritative-Version Resolver."""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class Document(BaseModel):
    document_id: str
    title: str
    department: str
    document_type: str = "Protocol"
    version: str
    content: str
    created_at: str
    effective_from: str
    effective_until: Optional[str] = None
    owner_id: str
    approval_id: Optional[str] = None
    status: str  # Approved, Draft, Pending, Superseded, Rejected
    access_level: str = "Staff"  # Staff, Clinical_Only, Restricted, Public
    supersedes_document_id: Optional[str] = None


class Approval(BaseModel):
    approval_id: str
    document_id: str
    approver_id: str
    approval_status: str  # Approved, Pending, Rejected
    approved_at: str
    approval_role: str


class Owner(BaseModel):
    owner_id: str
    department: str
    role: str
    authority_level: float = 1.0  # 1.0 = Primary, 0.7 = Secondary, 0.0 = Unauthorized
    active: bool = True


class AccessRule(BaseModel):
    document_id: str
    role: str  # Nurse, Physician, Pharmacist, Clinical_Admin, Visitor
    allowed: bool = True


class Citation(BaseModel):
    citation_id: str
    document_id: str
    version: str
    section_number: str
    section_title: str
    snippet: str


class ProtocolEvent(BaseModel):
    event_id: str
    timestamp: str
    type: str  # DOCUMENT_UPLOADED, DOCUMENT_APPROVED, DOCUMENT_DEPRECATED, DOCUMENT_SUPERSEDED
    document_id: str
    version: Optional[str] = None
    department: Optional[str] = None
    owner_id: Optional[str] = None
    approval_id: Optional[str] = None
    approver_id: Optional[str] = None
    approval_role: Optional[str] = None
    superseded_by: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None


class CandidateScore(BaseModel):
    document_id: str
    title: str
    version: str
    department: str
    status: str
    owner_id: str
    effective_from: str
    effective_until: Optional[str] = None
    similarity_score: float = 0.0
    approval_score: float = 0.0
    ownership_score: float = 0.0
    recency_score: float = 0.0
    version_score: float = 0.0
    access_score: float = 0.0
    authority_score: float = 0.0
    combined_score: float = 0.0
    rank: int = 1
    is_authoritative: bool = False
    is_access_allowed: bool = True
    explanation: str = ""


class ResolutionResult(BaseModel):
    selected_document: Optional[Document] = None
    candidate_scores: List[CandidateScore] = Field(default_factory=list)
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    hitl_required: bool = False
    status: str = "SUCCESS"  # SUCCESS, ACCESS_DENIED, NO_MATCH, AMBIGUOUS_HITL
    message: str = ""
    execution_time_ms: float = 0.0


class QueryResult(BaseModel):
    query: str
    user_role: str
    system_type: str  # "BASELINE" or "RESOLVER"
    selected_document_id: Optional[str] = None
    selected_version: Optional[str] = None
    selected_title: Optional[str] = None
    status: str = "SUCCESS"
    answer: str
    citation_text: str
    cited_section: Optional[str] = None
    authority_score: float = 0.0
    similarity_score: float = 0.0
    candidate_scores: List[CandidateScore] = Field(default_factory=list)
    hitl_required: bool = False
    explanation: str = ""


class HITLReviewItem(BaseModel):
    review_id: str
    query: str
    candidate_doc_ids: List[str]
    reason: str
    created_at: str
    status: str = "PENDING"  # PENDING, RESOLVED, DISMISSED
    resolved_by: Optional[str] = None
    resolved_doc_id: Optional[str] = None
    notes: Optional[str] = None


class StaffFeedback(BaseModel):
    feedback_id: str
    document_id: str
    user_role: str
    shift: str
    rating: int = Field(..., ge=1, le=5)
    feedback_category: str = "Clarity"  # Clarity, Usability, Safety, Outdated Info, Formatting
    comment: str
    timestamp: str
    sentiment_score: float = 0.5
    flag_for_review: bool = False


class ComplianceRecord(BaseModel):
    compliance_id: str
    document_id: str
    audit_status: str  # Compliant, Under Audit, Non-Compliant, Pending Renewal
    regulatory_body: str
    compliance_score: float = Field(1.0, ge=0.0, le=1.0)
    last_audit_date: str
    next_audit_due: str
    mandatory_training_required: bool = True
    signoff_officer: str

