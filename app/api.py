"""FastAPI Application for Hospital Protocol Authoritative-Version Resolver.

Provides RESTful endpoints for:
1. /api/resolve: Query resolution with deterministic authority scoring, access validation, and citation.
2. /api/compare: Side-by-side comparison of Naive Baseline vs. Authoritative Resolver.
3. /api/events/ingest: Idempotent protocol event ingestion (upload, approval, supersession).
4. /api/hitl/queue & /api/hitl/resolve: Human-in-the-loop clinical governance portal.
5. /api/metrics: Evaluation benchmark results and quantitative telemetry.
6. /api/documents: Current protocol inventory inspection.
"""

import os
import json
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.models import (
    Document,
    ProtocolEvent,
    QueryResult,
    ResolutionResult,
    HITLReviewItem,
    CandidateScore,
)
from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever, BaselineRetriever
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor
from src.resolver import AuthoritativeResolver
from src.rag import GroundedProtocolRAG

# Initialize FastAPI app
app = FastAPI(
    title="Hospital Protocol Authoritative-Version Resolver API",
    description="Deterministic Clinical Protocol Governance and Authoritative-Version Resolver",
    version="1.0.0",
)

# CORS middleware for interactive frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State Container
class SystemContainer:
    def __init__(self):
        self.loader = DataLoader()
        self.loader.load_all()

        self.state = ProtocolStateManager()
        for doc in self.loader.documents:
            self.state.add_document(doc)
        for app_rec in self.loader.approvals:
            self.state.add_approval(app_rec)
        for owner in self.loader.owners:
            self.state.add_owner(owner)
        for rule in self.loader.access_rules:
            self.state.set_access(rule.document_id, rule.role, rule.allowed)

        self.processor = EventProcessor(self.state)
        self.retriever = CandidateRetriever(self.state.get_all_documents())
        self.baseline = BaselineRetriever(self.retriever)
        self.resolver = AuthoritativeResolver(self.retriever, self.state)
        self.rag = GroundedProtocolRAG(self.loader.citations_by_doc)


container = SystemContainer()


# Request / Response Schemas
class ResolveRequest(BaseModel):
    query: str = Field(..., example="What is the current procedure for inpatient medication administration?")
    user_role: str = Field("Nurse", example="Nurse")
    shift: Optional[str] = Field("Day Shift", example="Night Shift")
    top_k: int = Field(5, ge=1, le=15)


class ResolveResponse(BaseModel):
    query: str
    user_role: str
    shift: str
    status: str
    selected_document: Optional[Dict[str, Any]]
    answer: str
    citation_text: str
    cited_section: Optional[str]
    authority_score: float
    similarity_score: float
    candidate_scores: List[CandidateScore]
    hitl_required: bool
    explanation: str
    execution_time_ms: float


class CompareResponse(BaseModel):
    query: str
    user_role: str
    baseline: Dict[str, Any]
    resolver: Dict[str, Any]
    divergence: bool
    divergence_reason: Optional[str]


class IngestEventRequest(BaseModel):
    event: ProtocolEvent


class HITLResolveRequest(BaseModel):
    review_id: str
    resolved_doc_id: str
    resolved_by: str = "Clinical Governance Committee"
    notes: Optional[str] = None


@app.get("/health")
def health_check():
    """Returns system health, document registry count, and loaded state."""
    return {
        "status": "HEALTHY",
        "service": "hospital-protocol-authoritative-resolver",
        "active_documents": len(container.state.documents),
        "active_owners": len(container.state.owners),
        "access_rules": len(container.state.access_map),
        "processed_events": len(container.state.processed_events),
        "pending_hitl_reviews": len([h for h in container.resolver.hitl_queue if h.status == "PENDING"]),
    }


@app.post("/api/resolve", response_model=ResolveResponse)
def resolve_query(req: ResolveRequest):
    """Resolves the current approved authoritative hospital protocol for a query and staff role."""
    resolution = container.resolver.resolve(
        query=req.query,
        user_role=req.user_role,
        top_k=req.top_k,
    )

    query_res = container.rag.answer_query(
        query=req.query,
        user_role=req.user_role,
        resolution=resolution,
        system_type="RESOLVER",
    )

    selected_doc_dict = resolution.selected_document.model_dump() if resolution.selected_document else None

    return ResolveResponse(
        query=req.query,
        user_role=req.user_role,
        shift=req.shift or "Day Shift",
        status=query_res.status,
        selected_document=selected_doc_dict,
        answer=query_res.answer,
        citation_text=query_res.citation_text,
        cited_section=query_res.cited_section,
        authority_score=query_res.authority_score,
        similarity_score=query_res.similarity_score,
        candidate_scores=query_res.candidate_scores,
        hitl_required=query_res.hitl_required,
        explanation=query_res.explanation,
        execution_time_ms=resolution.execution_time_ms,
    )


@app.get("/api/compare", response_model=CompareResponse)
def compare_query(query: str = Query(...), user_role: str = Query("Nurse")):
    """Compares naive baseline retrieval against authoritative resolver side-by-side."""
    # 1. Baseline
    base_doc, base_sim, base_cands = container.baseline.search(query)
    base_answer, base_citation, base_section = (
        container.rag.generate_grounded_answer(base_doc, query)
        if base_doc
        else ("No document retrieved", "None", "None")
    )
    base_access = (
        container.state.access_map.get((base_doc.document_id, user_role), True)
        if base_doc
        else True
    )

    baseline_data = {
        "selected_doc_id": base_doc.document_id if base_doc else None,
        "selected_version": base_doc.version if base_doc else None,
        "selected_title": base_doc.title if base_doc else None,
        "status": base_doc.status if base_doc else "None",
        "department": base_doc.department if base_doc else "None",
        "similarity_score": round(base_sim, 4),
        "access_allowed": base_access,
        "answer": base_answer,
        "citation": base_citation,
        "cited_section": base_section,
    }

    # 2. Resolver
    resolution = container.resolver.resolve(query, user_role=user_role)
    res_query_res = container.rag.answer_query(query, user_role, resolution)
    res_doc = resolution.selected_document

    resolver_data = {
        "selected_doc_id": res_doc.document_id if res_doc else None,
        "selected_version": res_doc.version if res_doc else None,
        "selected_title": res_doc.title if res_doc else None,
        "status": res_doc.status if res_doc else resolution.status,
        "department": res_doc.department if res_doc else "None",
        "resolution_status": resolution.status,
        "authority_score": res_query_res.authority_score,
        "similarity_score": res_query_res.similarity_score,
        "answer": res_query_res.answer,
        "citation": res_query_res.citation_text,
        "cited_section": res_query_res.cited_section,
    }

    # 3. Analyze Divergence
    divergence = False
    divergence_reason = None

    if base_doc and not res_doc:
        divergence = True
        divergence_reason = f"Baseline served unverified/restricted document '{base_doc.document_id}', while Resolver correctly blocked it ({resolution.status})."
    elif base_doc and res_doc and base_doc.document_id != res_doc.document_id:
        divergence = True
        divergence_reason = (
            f"Baseline chose '{base_doc.document_id}' ({base_doc.status} v{base_doc.version}) due to keyword similarity ({base_sim:.3f}), "
            f"whereas Resolver identified authoritative '{res_doc.document_id}' ({res_doc.status} v{res_doc.version}, Authority: {res_query_res.authority_score:.3f})."
        )
    elif base_doc and base_doc.status == "Draft":
        divergence = True
        divergence_reason = "Baseline served an unapproved Draft document directly to clinical staff."

    return CompareResponse(
        query=query,
        user_role=user_role,
        baseline=baseline_data,
        resolver=resolver_data,
        divergence=divergence,
        divergence_reason=divergence_reason,
    )


@app.post("/api/events/ingest")
def ingest_event(req: IngestEventRequest):
    """Idempotently ingests a protocol event into the state manager."""
    ok, msg = container.processor.process_event(req.event)
    # Update retriever index if new document was registered or version updated
    container.retriever.update_documents(container.state.get_all_documents())

    return {
        "event_id": req.event.event_id,
        "type": req.event.type,
        "processed": ok,
        "message": msg,
        "total_active_documents": len(container.state.documents),
        "total_events_processed": len(container.state.processed_events),
    }


@app.get("/api/hitl/queue")
def get_hitl_queue():
    """Retrieves all human-in-the-loop review items."""
    return [item.model_dump() for item in container.resolver.hitl_queue]


@app.post("/api/hitl/resolve")
def resolve_hitl_item(req: HITLResolveRequest):
    """Resolves an ambiguous review item by clinical governance action."""
    for item in container.resolver.hitl_queue:
        if item.review_id == req.review_id:
            item.status = "RESOLVED"
            item.resolved_by = req.resolved_by
            item.resolved_doc_id = req.resolved_doc_id
            item.notes = req.notes
            return {"status": "SUCCESS", "message": f"Review {req.review_id} resolved.", "item": item.model_dump()}

    raise HTTPException(status_code=404, detail=f"Review ID '{req.review_id}' not found.")


@app.get("/api/metrics")
def get_metrics():
    """Returns the evaluation metrics from summary_metrics.json."""
    metrics_path = os.path.join(os.path.dirname(__file__), "..", "experiments", "summary_metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path, "r") as f:
            return json.load(f)
    return {"message": "Metrics not yet calculated. Run python -m src.evaluation"}


@app.get("/api/documents")
def list_documents():
    """Returns all current documents stored in the state manager."""
    return [doc.model_dump() for doc in container.state.get_all_documents()]
