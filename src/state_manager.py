"""State Manager Module for Hospital Protocol Registry.

Maintains an in-memory, reproducible state of:
- Documents
- Approvals
- Owners
- Access rules
- Processed events (for idempotency)
- Event history
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from copy import deepcopy
from src.models import Document, Approval, Owner, AccessRule, ProtocolEvent, StaffFeedback, ComplianceRecord
from src.ranking import parse_semver


class ProtocolStateManager:
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.approvals: Dict[str, Approval] = {}
        self.owners: Dict[str, Owner] = {}
        self.access_map: Dict[Tuple[str, str], bool] = {}
        self.processed_events: Set[str] = set()
        self.event_history: List[ProtocolEvent] = []
        self.staff_feedback: List[StaffFeedback] = []
        self.compliance_records: Dict[str, ComplianceRecord] = {}

    def clone(self) -> "ProtocolStateManager":
        """Creates an independent clone of the state manager for testing / simulation."""
        cloned = ProtocolStateManager()
        cloned.documents = deepcopy(self.documents)
        cloned.approvals = deepcopy(self.approvals)
        cloned.owners = deepcopy(self.owners)
        cloned.access_map = deepcopy(self.access_map)
        cloned.processed_events = set(self.processed_events)
        cloned.event_history = list(self.event_history)
        cloned.staff_feedback = deepcopy(self.staff_feedback)
        cloned.compliance_records = deepcopy(self.compliance_records)
        return cloned

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self.processed_events

    def mark_event_processed(self, event_id: str):
        self.processed_events.add(event_id)

    def add_document(self, doc: Document):
        self.documents[doc.document_id] = doc

    def add_approval(self, app: Approval):
        self.approvals[app.approval_id] = app

    def add_owner(self, owner: Owner):
        self.owners[owner.owner_id] = owner

    def set_access(self, doc_id: str, role: str, allowed: bool):
        self.access_map[(doc_id, role)] = allowed

    def add_staff_feedback(self, fb: StaffFeedback):
        self.staff_feedback.append(fb)

    def get_feedback_for_document(self, doc_id: str) -> List[StaffFeedback]:
        return [fb for fb in self.staff_feedback if fb.document_id == doc_id]

    def get_feedback_summary_for_doc(self, doc_id: str) -> Dict[str, Any]:
        items = self.get_feedback_for_document(doc_id)
        if not items:
            return {"total_reviews": 0, "avg_rating": 0.0, "avg_sentiment": 0.0, "flagged_count": 0}
        avg_rating = sum(fb.rating for fb in items) / len(items)
        avg_sentiment = sum(fb.sentiment_score for fb in items) / len(items)
        flagged = sum(1 for fb in items if fb.flag_for_review)
        return {
            "total_reviews": len(items),
            "avg_rating": round(avg_rating, 2),
            "avg_sentiment": round(avg_sentiment, 2),
            "flagged_count": flagged,
        }

    def set_compliance_record(self, record: ComplianceRecord):
        self.compliance_records[record.document_id] = record

    def get_compliance_record(self, doc_id: str) -> Optional[ComplianceRecord]:
        return self.compliance_records.get(doc_id)


    def get_document(self, doc_id: str) -> Optional[Document]:
        return self.documents.get(doc_id)

    def get_all_documents(self) -> List[Document]:
        return list(self.documents.values())

    def get_active_approved_version(self, protocol_title: str) -> Optional[Document]:
        """Returns the current active approved document for a protocol title,

        ensuring monotonic version selection and supersession adherence.
        """
        candidates = [
            doc for doc in self.documents.values()
            if doc.title.lower() == protocol_title.lower()
            and doc.status.strip().title() == "Approved"
        ]
        if not candidates:
            return None

        # Filter out documents explicitly marked as superseded or with valid successor
        superseded_ids = {
            doc.supersedes_document_id for doc in candidates if doc.supersedes_document_id
        }

        # Keep non-superseded candidates
        active_candidates = [
            doc for doc in candidates if doc.document_id not in superseded_ids
        ]

        if not active_candidates:
            active_candidates = candidates

        # Pick highest version with primary ownership
        active_candidates.sort(
            key=lambda d: (
                1 if self.owners.get(d.owner_id, Owner(owner_id="", department="", role="", authority_level=0.0)).authority_level >= 1.0 else 0,
                parse_semver(d.version)
            ),
            reverse=True,
        )
        return active_candidates[0]
