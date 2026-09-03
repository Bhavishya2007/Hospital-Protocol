"""State Manager Module for Hospital Protocol Registry.

Maintains an in-memory, reproducible state of:
- Documents
- Approvals
- Owners
- Access rules
- Processed events (for idempotency)
- Event history
"""

from typing import Dict, List, Set, Tuple, Optional
from copy import deepcopy
from src.models import Document, Approval, Owner, AccessRule, ProtocolEvent
from src.ranking import parse_semver


class ProtocolStateManager:
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.approvals: Dict[str, Approval] = {}
        self.owners: Dict[str, Owner] = {}
        self.access_map: Dict[Tuple[str, str], bool] = {}
        self.processed_events: Set[str] = set()
        self.event_history: List[ProtocolEvent] = []

    def clone(self) -> "ProtocolStateManager":
        """Creates an independent clone of the state manager for testing / simulation."""
        cloned = ProtocolStateManager()
        cloned.documents = deepcopy(self.documents)
        cloned.approvals = deepcopy(self.approvals)
        cloned.owners = deepcopy(self.owners)
        cloned.access_map = deepcopy(self.access_map)
        cloned.processed_events = set(self.processed_events)
        cloned.event_history = list(self.event_history)
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
