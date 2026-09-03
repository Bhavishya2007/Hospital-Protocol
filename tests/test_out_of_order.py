"""Test failure case 3: Out-of-order events.

Scenario:
Events arrive:
1. v3 Approved
2. v5 Uploaded
3. v4 Uploaded (arrives out-of-order after v5)

Expected final state:
Version 5 remains the authoritative state and is NOT corrupted or downgraded by v4.
"""

import pytest
from src.models import ProtocolEvent, Document, Owner
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor
from src.retrieval import CandidateRetriever
from src.resolver import AuthoritativeResolver


def test_out_of_order_events_preserves_higher_version():
    state = ProtocolStateManager()
    state.add_owner(Owner(owner_id="OWNER_NURSING", department="Nursing", role="Head", authority_level=1.0))
    state.set_access("DOC-OOO-100", "Nurse", True)
    processor = EventProcessor(state)

    # 1. Event 1: v3 Approved
    e1 = ProtocolEvent(
        event_id="EVT-O-01",
        timestamp="2026-08-01T10:00:00Z",
        type="DOCUMENT_UPLOADED",
        document_id="DOC-OOO-100",
        version="3.0",
        title="Out of Order Protocol",
        department="Nursing",
        owner_id="OWNER_NURSING",
        status="Approved",
    )
    processor.process_event(e1)

    # 2. Event 2: v5 Uploaded (Approved)
    e2 = ProtocolEvent(
        event_id="EVT-O-02",
        timestamp="2026-08-20T10:00:00Z",
        type="DOCUMENT_UPLOADED",
        document_id="DOC-OOO-100",
        version="5.0",
        title="Out of Order Protocol",
        department="Nursing",
        owner_id="OWNER_NURSING",
        status="Approved",
    )
    processor.process_event(e2)

    # 3. Event 3: v4 Uploaded (Out of order older update arriving late)
    e3 = ProtocolEvent(
        event_id="EVT-O-03",
        timestamp="2026-08-10T10:00:00Z",
        type="DOCUMENT_UPLOADED",
        document_id="DOC-OOO-100",
        version="4.0",
        title="Out of Order Protocol",
        department="Nursing",
        owner_id="OWNER_NURSING",
        status="Approved",
    )
    processor.process_event(e3)

    # Check state monotonicity
    doc = state.get_document("DOC-OOO-100")
    assert doc is not None
    assert doc.version == "5.0", f"Expected version 5.0, but found version {doc.version} (corrupted by out-of-order event)"

    # Check resolver
    retriever = CandidateRetriever(state.get_all_documents())
    resolver = AuthoritativeResolver(retriever, state)
    res = resolver.resolve("Out of Order Protocol", user_role="Nurse")

    assert res.selected_document is not None
    assert res.selected_document.version == "5.0"
