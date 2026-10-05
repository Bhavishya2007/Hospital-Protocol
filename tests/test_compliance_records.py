"""Unit tests for Dedicated Compliance Records & Audit Verification."""

import pytest
from src.data_loader import DataLoader
from src.state_manager import ProtocolStateManager
from src.retrieval import CandidateRetriever
from src.resolver import AuthoritativeResolver
from src.models import ComplianceRecord, Document, Owner


def test_compliance_records_loading():
    loader = DataLoader()
    loader.load_all()

    assert len(loader.compliance_records) > 0, "Compliance records should load from compliance_records.csv"
    comp = loader.compliance_by_doc.get("DOC-MED-004")
    assert comp is not None
    assert comp.audit_status == "Compliant"
    assert comp.regulatory_body == "The Joint Commission"
    assert comp.compliance_score == 1.0


def test_non_compliant_protocol_gating():
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
    for doc_id, comp in loader.compliance_by_doc.items():
        state.set_compliance_record(comp)

    # Inject a non-compliant audit status for DOC-MED-004
    non_comp = ComplianceRecord(
        compliance_id="CMP-TEST-99",
        document_id="DOC-MED-004",
        audit_status="Non-Compliant",
        regulatory_body="Joint Commission Safety Audit",
        compliance_score=0.20,
        last_audit_date="2026-09-01",
        next_audit_due="2026-09-15",
        mandatory_training_required=True,
        signoff_officer="Safety Auditor",
    )
    state.set_compliance_record(non_comp)

    retriever = CandidateRetriever(state.get_all_documents())
    resolver = AuthoritativeResolver(retriever, state)

    result = resolver.resolve("What is the procedure for inpatient medication administration?", user_role="Nurse", top_k=10)

    # Because DOC-MED-004 is marked Non-Compliant, its authority score should be gated to <= 0.30
    cand_004 = next((c for c in result.candidate_scores if c.document_id == "DOC-MED-004"), None)
    assert cand_004 is not None
    assert cand_004.authority_score <= 0.30
    assert "GATED (non-compliant" in cand_004.explanation
