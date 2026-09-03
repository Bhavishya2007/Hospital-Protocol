"""Test failure case 1: Draft newer version vs Approved older version.

Invariant: Higher version number alone must NEVER override approval status.
A draft with version 4.0 and high keyword similarity must NOT beat Approved version 3.1.
"""

import pytest
from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever, BaselineRetriever
from src.state_manager import ProtocolStateManager
from src.resolver import AuthoritativeResolver


def test_draft_v4_does_not_beat_approved_v31():
    loader = DataLoader()
    loader.load_all()

    state = ProtocolStateManager()
    for doc in loader.documents:
        state.add_document(doc)
    for app in loader.approvals:
        state.add_approval(app)
    for owner in loader.owners:
        state.add_owner(owner)
    for rule in loader.access_rules:
        state.set_access(rule.document_id, rule.role, rule.allowed)

    retriever = CandidateRetriever(loader.documents)
    baseline = BaselineRetriever(retriever)
    resolver = AuthoritativeResolver(retriever, state)

    # Query targeting keywords that exist in both Draft v4 and Approved v3.1
    query = "high performance CPR biphasic defibrillation shock energy and epinephrine dosing"

    # Resolver execution
    res = resolver.resolve(query, user_role="Physician")

    assert res.status == "SUCCESS"
    assert res.selected_document is not None
    # Must select Approved v4.0 (DOC-CPR-002), NEVER Draft v5.0 (DOC-CPR-003)
    assert res.selected_document.document_id == "DOC-CPR-002"
    assert res.selected_document.version == "4.0"
    assert res.selected_document.status == "Approved"

    # Verify Draft candidate was penalized and gated below approved candidate
    scores = {c.document_id: c for c in res.candidate_scores}
    if "DOC-CPR-003" in scores:
        draft_cand = scores["DOC-CPR-003"]
        approved_cand = scores["DOC-CPR-002"]
        assert draft_cand.status == "Draft"
        assert draft_cand.authority_score <= 0.35
        assert approved_cand.authority_score >= 0.70
        assert approved_cand.combined_score > draft_cand.combined_score
