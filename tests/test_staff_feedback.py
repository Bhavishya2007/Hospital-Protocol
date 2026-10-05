"""Unit tests for Staff Feedback Capture & Structured Data Input."""

import pytest
from src.data_loader import DataLoader
from src.state_manager import ProtocolStateManager
from src.models import StaffFeedback


def test_staff_feedback_loading():
    loader = DataLoader()
    loader.load_all()
    
    assert len(loader.staff_feedback) > 0, "Staff feedback should load records from staff_feedback.csv"
    fb = loader.staff_feedback[0]
    assert isinstance(fb, StaffFeedback)
    assert fb.document_id != ""
    assert 1 <= fb.rating <= 5


def test_staff_feedback_state_management():
    state = ProtocolStateManager()
    
    fb1 = StaffFeedback(
        feedback_id="FB-TEST-001",
        document_id="DOC-MED-004",
        user_role="Nurse",
        shift="Day Shift",
        rating=5,
        feedback_category="Clarity",
        comment="Dual verification instructions are extremely clear.",
        timestamp="2026-09-25T10:00:00",
        sentiment_score=0.95,
        flag_for_review=False,
    )
    
    fb2 = StaffFeedback(
        feedback_id="FB-TEST-002",
        document_id="DOC-MED-004",
        user_role="Pharmacist",
        shift="Night Shift",
        rating=1,
        feedback_category="Safety",
        comment="Potential dosing confusion in Section 4.",
        timestamp="2026-09-25T11:00:00",
        sentiment_score=0.10,
        flag_for_review=True,
    )

    state.add_staff_feedback(fb1)
    state.add_staff_feedback(fb2)

    doc_feedback = state.get_feedback_for_document("DOC-MED-004")
    assert len(doc_feedback) == 2

    summary = state.get_feedback_summary_for_doc("DOC-MED-004")
    assert summary["total_reviews"] == 2
    assert summary["avg_rating"] == 3.0
    assert summary["flagged_count"] == 1
