"""Test failure case 5: Wrong owner / unauthorized department.

Scenario:
- Department A (Nursing, official owner) uploads v5 (Approved).
- Department B (Facilities, unauthorized) uploads v6 (Approved).

Expected:
Resolver identifies Department A as official owner (authority level 1.0)
and Department B as unauthorized (authority level 0.2), thus selecting Department A v5.
"""

import pytest
from src.data_loader import DataLoader
from src.models import Document, Owner
from src.retrieval import CandidateRetriever
from src.state_manager import ProtocolStateManager
from src.resolver import AuthoritativeResolver


def test_unauthorized_department_rejected():
    state = ProtocolStateManager()
    state.add_owner(Owner(owner_id="OWNER_NURSING", department="Nursing", role="Head", authority_level=1.0))
    state.add_owner(Owner(owner_id="OWNER_FACILITIES", department="Facilities", role="Supervisor", authority_level=0.2))

    # Official Nursing protocol v5.0 Approved
    doc_nursing = Document(
        document_id="DOC-DEPT-NURSE-05",
        title="Medication Administration Safety Protocol",
        department="Nursing",
        version="5.0",
        content="Official nursing medication safety procedures and double signoff rules.",
        created_at="2026-08-01",
        effective_from="2026-08-01",
        owner_id="OWNER_NURSING",
        status="Approved",
    )
    # Unauthorized Facilities protocol v6.0 Approved
    doc_facilities = Document(
        document_id="DOC-DEPT-FACIL-06",
        title="Medication Administration Safety Protocol",
        department="Facilities",
        version="6.0",
        content="Facilities medication lockbox key management guidelines.",
        created_at="2026-08-15",
        effective_from="2026-08-15",
        owner_id="OWNER_FACILITIES",
        status="Approved",
    )

    state.add_document(doc_nursing)
    state.add_document(doc_facilities)
    state.set_access("DOC-DEPT-NURSE-05", "Nurse", True)
    state.set_access("DOC-DEPT-FACIL-06", "Nurse", True)

    retriever = CandidateRetriever(state.get_all_documents())
    resolver = AuthoritativeResolver(retriever, state)

    res = resolver.resolve("Medication Administration Safety Protocol double signoff", user_role="Nurse")

    assert res.status == "SUCCESS"
    assert res.selected_document is not None
    assert res.selected_document.document_id == "DOC-DEPT-NURSE-05"
    assert res.selected_document.department == "Nursing"
    assert res.selected_document.version == "5.0"
