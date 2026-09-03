"""Authoritative-Version Resolver Module.

Orchestrates:
1. Candidate retrieval
2. Multi-factor authority scoring
3. Invariant gating (Drafts capped, access evaluated)
4. Ambiguity / conflict detection & Human-in-the-Loop (HITL) routing
5. Selection of current approved authoritative document
"""

import time
from typing import List, Tuple, Optional, Dict
from src.models import (
    Document,
    Owner,
    CandidateScore,
    ResolutionResult,
    HITLReviewItem,
)
from src.retrieval import CandidateRetriever
from src.ranking import rank_candidates, parse_semver
from src.state_manager import ProtocolStateManager


class AuthoritativeResolver:
    def __init__(
        self,
        retriever: CandidateRetriever,
        state_manager: ProtocolStateManager,
    ):
        self.retriever = retriever
        self.state_manager = state_manager
        self.hitl_queue: List[HITLReviewItem] = []

    def resolve(
        self,
        query: str,
        user_role: str = "Nurse",
        top_k: int = 5,
    ) -> ResolutionResult:
        """Resolves the current authoritative protocol document for the query."""
        start_time = time.perf_counter()

        # Step 1: Candidate retrieval
        candidates = self.retriever.retrieve_candidates(query, top_k=top_k)
        if not candidates:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ResolutionResult(
                selected_document=None,
                candidate_scores=[],
                is_ambiguous=False,
                status="NO_MATCH",
                message="No protocol candidates matched the query.",
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Step 2: Multi-factor authority ranking
        ranked_scores = rank_candidates(
            candidates=candidates,
            owners_by_id=self.state_manager.owners,
            access_map=self.state_manager.access_map,
            user_role=user_role,
        )

        top_cand = ranked_scores[0]

        # Step 3: Access Control Validation
        if not top_cand.is_access_allowed:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ResolutionResult(
                selected_document=None,
                candidate_scores=ranked_scores,
                is_ambiguous=False,
                status="ACCESS_DENIED",
                message=f"Access Denied: Role '{user_role}' is not authorized to view {top_cand.title} ({top_cand.document_id}).",
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Step 4: Check for Ambiguity / Equal-Authority Conflict (HITL trigger)
        is_ambiguous = False
        ambiguity_reason = None
        hitl_required = False

        if len(ranked_scores) > 1:
            second_cand = ranked_scores[1]
            score_diff = abs(top_cand.combined_score - second_cand.combined_score)

            # Conflict scenario: Two approved versions with conflicting guidance or near-identical authority score
            if (
                top_cand.status == "Approved"
                and second_cand.status == "Approved"
                and second_cand.is_access_allowed
                and score_diff < 0.04
                and top_cand.version != second_cand.version
            ):
                is_ambiguous = True
                hitl_required = True
                ambiguity_reason = (
                    f"Conflicting approved protocols detected: "
                    f"'{top_cand.document_id}' (v{top_cand.version}, score {top_cand.combined_score:.3f}) vs "
                    f"'{second_cand.document_id}' (v{second_cand.version}, score {second_cand.combined_score:.3f}). "
                    f"Escalating to Clinical Governance."
                )

        if is_ambiguous:
            # Enqueue for human review
            review_item = HITLReviewItem(
                review_id=f"HITL-{len(self.hitl_queue) + 1:04d}",
                query=query,
                candidate_doc_ids=[top_cand.document_id, second_cand.document_id],
                reason=ambiguity_reason or "Score tie among approved protocols",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            self.hitl_queue.append(review_item)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ResolutionResult(
                selected_document=self.state_manager.get_document(top_cand.document_id),
                candidate_scores=ranked_scores,
                is_ambiguous=True,
                ambiguity_reason=ambiguity_reason,
                hitl_required=True,
                status="AMBIGUOUS_HITL",
                message=f"Ambiguity detected: {ambiguity_reason}",
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Step 5: Check if top candidate qualifies as authoritative
        selected_doc = self.state_manager.get_document(top_cand.document_id)
        if top_cand.authority_score < 0.50 or top_cand.status != "Approved":
            # No valid approved document found
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ResolutionResult(
                selected_document=None,
                candidate_scores=ranked_scores,
                is_ambiguous=False,
                status="NO_APPROVED_VERSION",
                message=(
                    f"Warning: Top candidate '{top_cand.title}' v{top_cand.version} is '{top_cand.status}'. "
                    f"No approved authoritative protocol is available for this query."
                ),
                execution_time_ms=round(elapsed_ms, 2),
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return ResolutionResult(
            selected_document=selected_doc,
            candidate_scores=ranked_scores,
            is_ambiguous=False,
            ambiguity_reason=None,
            hitl_required=False,
            status="SUCCESS",
            message=f"Authoritative protocol identified: {selected_doc.title} v{selected_doc.version} ({selected_doc.status})",
            execution_time_ms=round(elapsed_ms, 2),
        )
