"""Test failure case 2: Duplicate event arrival and idempotency.

Invariant:
If an event (e.g. DOC_UPDATE_101) arrives multiple times,
the state must be mutated exactly once, preserving idempotency without duplicate entities.
"""

import pytest
from src.models import ProtocolEvent, Document
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor


def test_duplicate_event_is_idempotent():
    state = ProtocolStateManager()
    processor = EventProcessor(state)

    event = ProtocolEvent(
        event_id="DOC_UPDATE_101",
        timestamp="2026-09-01T12:00:00Z",
        type="DOCUMENT_UPLOADED",
        document_id="DOC-DUP-999",
        version="1.0",
        title="Duplicate Test Protocol",
        department="Emergency Medicine",
        owner_id="OWNER_EMERGENCY",
        status="Draft",
    )

    # First ingestion
    ok1, msg1 = processor.process_event(event)
    assert ok1 is True
    assert "Registered new document" in msg1
    assert state.is_event_processed("DOC_UPDATE_101")
    assert len([d for d in state.get_all_documents() if d.document_id == "DOC-DUP-999"]) == 1

    # Second ingestion (Duplicate)
    ok2, msg2 = processor.process_event(event)
    assert ok2 is True
    assert "already processed. Idempotent skip." in msg2
    assert len([d for d in state.get_all_documents() if d.document_id == "DOC-DUP-999"]) == 1

    # Third ingestion (Duplicate)
    ok3, msg3 = processor.process_event(event)
    assert ok3 is True
    assert "already processed. Idempotent skip." in msg3
    assert len([d for d in state.get_all_documents() if d.document_id == "DOC-DUP-999"]) == 1

    # Event history contains only one entry
    assert len(state.event_history) == 1
