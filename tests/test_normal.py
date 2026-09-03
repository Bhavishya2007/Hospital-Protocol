"""Test normal clinical queries resolving to the current approved protocol with valid citations."""

import pytest
from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever
from src.state_manager import ProtocolStateManager
from src.resolver import AuthoritativeResolver
from src.rag import GroundedProtocolRAG


@pytest.fixture
def system():
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
    return resolver, rag


def test_medication_administration_normal_query(system):
    resolver, rag = system
    query = "What is the procedure for inpatient medication administration and five rights verification?"
    res = resolver.resolve(query, user_role="Nurse")

    assert res.status == "SUCCESS"
    assert res.selected_document is not None
    assert res.selected_document.document_id == "DOC-MED-004"
    assert res.selected_document.version == "3.1"
    assert res.selected_document.status == "Approved"

    query_res = rag.answer_query(query, "Nurse", res)
    assert query_res.status == "SUCCESS"
    assert "Section 2" in query_res.cited_section
    assert "Five Rights" in query_res.answer


def test_infection_control_normal_query(system):
    resolver, rag = system
    query = "What is the current infection control procedure for hand hygiene and PPE?"
    res = resolver.resolve(query, user_role="Nurse")

    assert res.status == "SUCCESS"
    assert res.selected_document is not None
    assert res.selected_document.document_id == "DOC-INF-003"
    assert res.selected_document.version == "2.1"
    assert res.selected_document.status == "Approved"
