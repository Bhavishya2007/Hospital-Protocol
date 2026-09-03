"""Test failure case 4: Delayed approval event.

Scenario:
1. v3 is currently Approved and Authoritative.
2. v4 is uploaded (Draft status).
3. Approval event for v4 arrives with delay.

Expected:
- Before approval event: queries resolve to v3 (Authoritative).
- After approval event: queries immediately resolve to v4 (Authoritative).
"""

import pytest
from src.models import ProtocolEvent, Document, Owner
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor
from src.retrieval import CandidateRetriever
from src.resolver import AuthoritativeResolver


def test_delayed_approval_lifecycle():
    state = ProtocolStateManager()
    state.add_owner(Owner(owner_id="OWNER_NURSING", department="Nursing", role="Head", authority_level=1.0))
    processor = EventProcessor(state)

    # Initial approved state: v3.0
    doc_v3 = Document(
        document_id="DOC-DELAY-V3",
        title="Emergency Delayed Protocol",
        department="Nursing",
        version="3.0",
        content="Section 1: Initial stable clinical guidelines for protocol v3.",
        created_at="2026-01-01",
        effective_from="2026-01-01",
        owner_id="OWNER_NURSING",
        status="Approved",
    )
    state.add_document(doc_v3)
    state.set_access("DOC-DELAY-V3", "Nurse", True)

    # Step 1: Upload v4 (Draft)
    evt_v4_up = ProtocolEvent(
        event_id="EVT-DELAY-V4-UP",
        timestamp="2026-08-20T10:00:00Z",
        type="DOCUMENT_UPLOADED",
        document_id="DOC-DELAY-V4",
        version="4.0",
        title="Emergency Delayed Protocol",
        department="Nursing",
        owner_id="OWNER_NURSING",
        status="Draft",
    )
    processor.process_event(evt_v4_up)
    state.set_access("DOC-DELAY-V4", "Nurse", True)

    # Step 2: Query BEFORE delayed approval arrives
    retriever = CandidateRetriever(state.get_all_documents())
    resolver = AuthoritativeResolver(retriever, state)

    res_before = resolver.resolve("Emergency Delayed Protocol", user_role="Nurse")
    assert res_before.status == "SUCCESS"
    assert res_before.selected_document is not None
    assert res_before.selected_document.version == "3.0", (
        f"Expected v3.0 to be authoritative before approval, but got {res_before.selected_document.version}"
    )

    # Step 3: Delayed approval event arrives!
    evt_v4_app = ProtocolEvent(
        event_id="EVT-DELAY-V4-APP",
        timestamp="2026-08-30T10:00:00Z",
        type="DOCUMENT_APPROVED",
        document_id="DOC-DELAY-V4",
        version="4.0",
        approval_role="Chief Medical Officer",
    )
    processor.process_event(evt_v4_app)

    # Step 4: Query AFTER delayed approval arrives
    retriever.update_documents(state.get_all_documents())
    res_after = resolver.resolve("Emergency Delayed Protocol", user_role="Nurse")

    assert res_after.status == "SUCCESS"
    assert res_after.selected_document is not None
    assert res_after.selected_document.version == "4.0", (
        f"Expected v4.0 to become authoritative after approval, but got {res_after.selected_document.version}"
    )
    assert res_after.selected_document.status == "Approved"
