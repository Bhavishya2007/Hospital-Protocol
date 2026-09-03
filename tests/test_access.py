"""Test failure case 6: Unauthorized document access control.

Scenario:
- Document is Approved, current version, correct owner.
- User role is 'Visitor' (or unpermitted role).
- Document has access_rules.csv mapping Visitor: False.

Expected:
System identifies access violation and refuses to serve the document (DO NOT USE DOCUMENT).
Returns ACCESS_DENIED status.
"""

import pytest
from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever
from src.state_manager import ProtocolStateManager
from src.resolver import AuthoritativeResolver
from src.rag import GroundedProtocolRAG


def test_access_denied_for_unauthorized_role():
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
    resolver = AuthoritativeResolver(retriever, state)
    rag = GroundedProtocolRAG(loader.citations_by_doc)

    # 1. Visitor attempts to access narcotic waste protocol
    query = "How do I access and dispose of controlled substance narcotics in the pharmacy?"
    res_visitor = resolver.resolve(query, user_role="Visitor")

    assert res_visitor.status == "ACCESS_DENIED"
    assert res_visitor.selected_document is None

    rag_res = rag.answer_query(query, "Visitor", res_visitor)
    assert rag_res.status == "ACCESS_DENIED"
    assert "ACCESS DENIED" in rag_res.answer

    # 2. Authorized Pharmacist performs the same query -> SUCCESS
    res_pharmacist = resolver.resolve(query, user_role="Pharmacist")
    assert res_pharmacist.status == "SUCCESS"
    assert res_pharmacist.selected_document is not None
    assert res_pharmacist.selected_document.document_id == "DOC-PHARM-001"
