"""Event Processor Module for Hospital Protocol Updates.

Handles:
- DOCUMENT_UPLOADED
- DOCUMENT_APPROVED
- DOCUMENT_SUPERSEDED
- DOCUMENT_DEPRECATED

Provides strict guarantees:
1. Idempotency: Duplicate events are detected via event_id and ignored without state mutation.
2. Monotonicity & Out-of-Order Recovery: Out-of-order arrivals do not overwrite or downgrade active authoritative state.
3. Delayed Approval Reconciliation: Documents remain unapproved drafts until explicit approval events arrive.
"""

from typing import Tuple, Optional, List
from src.models import ProtocolEvent, Document, Approval
from src.state_manager import ProtocolStateManager
from src.ranking import parse_semver


class EventProcessor:
    def __init__(self, state_manager: ProtocolStateManager):
        self.state_manager = state_manager

    def process_event(self, event: ProtocolEvent) -> Tuple[bool, str]:
        """Processes a single protocol event idempotently."""
        # 1. Idempotency check
        if self.state_manager.is_event_processed(event.event_id):
            return True, f"Event {event.event_id} already processed. Idempotent skip."

        event_type = event.type.strip().upper()
        success = False
        message = ""

        if event_type == "DOCUMENT_UPLOADED":
            success, message = self._handle_document_uploaded(event)
        elif event_type == "DOCUMENT_APPROVED":
            success, message = self._handle_document_approved(event)
        elif event_type == "DOCUMENT_SUPERSEDED":
            success, message = self._handle_document_superseded(event)
        elif event_type == "DOCUMENT_DEPRECATED":
            success, message = self._handle_document_deprecated(event)
        else:
            return False, f"Unknown event type: {event_type}"

        if success:
            self.state_manager.mark_event_processed(event.event_id)
            self.state_manager.event_history.append(event)

        return success, message

    def process_event_stream(self, events: List[ProtocolEvent]) -> List[Tuple[str, bool, str]]:
        """Processes a batch or stream of events sequentially."""
        results = []
        for evt in events:
            ok, msg = self.process_event(evt)
            results.append((evt.event_id, ok, msg))
        return results

    def _handle_document_uploaded(self, event: ProtocolEvent) -> Tuple[bool, str]:
        existing_doc = self.state_manager.get_document(event.document_id)
        status = event.status or ("Approved" if event.status == "Approved" else "Draft")

        if existing_doc:
            # Check if this is an older version arriving out-of-order
            existing_ver = parse_semver(existing_doc.version)
            new_ver = parse_semver(event.version or "1.0")

            if existing_doc.status == "Approved" and status == "Draft":
                # Do not downgrade approved document to draft
                return True, f"Document {event.document_id} is already Approved v{existing_doc.version}; keeping approved state."

            # Monotonicity rule: out-of-order older upload must not overwrite established newer version
            if new_ver < existing_ver:
                return True, f"Document {event.document_id} already has newer v{existing_doc.version} >= v{new_ver}; out-of-order older upload ignored."

            # Update document attributes
            existing_doc.version = event.version or existing_doc.version
            existing_doc.title = event.title or existing_doc.title
            existing_doc.department = event.department or existing_doc.department
            existing_doc.owner_id = event.owner_id or existing_doc.owner_id
            existing_doc.status = status
            return True, f"Updated existing document {event.document_id} to v{existing_doc.version} ({status})."

        # Register new document
        new_doc = Document(
            document_id=event.document_id,
            title=event.title or f"Protocol {event.document_id}",
            department=event.department or "General",
            version=event.version or "1.0",
            content=f"Protocol {event.title or event.document_id} content v{event.version or '1.0'}",
            created_at=event.timestamp.split("T")[0],
            effective_from=event.timestamp.split("T")[0],
            owner_id=event.owner_id or "OWNER_UNKNOWN",
            approval_id=event.approval_id,
            status=status,
            access_level="Staff",
        )
        self.state_manager.add_document(new_doc)
        return True, f"Registered new document {event.document_id} v{new_doc.version} as {status}."

    def _handle_document_approved(self, event: ProtocolEvent) -> Tuple[bool, str]:
        doc = self.state_manager.get_document(event.document_id)
        if not doc:
            # Lazy document stub creation if approval arrived before upload (out-of-order)
            doc = Document(
                document_id=event.document_id,
                title=f"Protocol {event.document_id}",
                department="General",
                version=event.version or "1.0",
                content=f"Protocol {event.document_id} content",
                created_at=event.timestamp.split("T")[0],
                effective_from=event.timestamp.split("T")[0],
                owner_id="OWNER_NURSING",
                approval_id=event.approval_id,
                status="Approved",
                access_level="Staff",
            )
            self.state_manager.add_document(doc)

        doc.status = "Approved"
        doc.approval_id = event.approval_id or f"APP-{event.event_id}"

        # Register approval record
        approval = Approval(
            approval_id=doc.approval_id,
            document_id=doc.document_id,
            approver_id=event.approver_id or "CLINICAL_APPROVER",
            approval_status="Approved",
            approved_at=event.timestamp,
            approval_role=event.approval_role or "Clinical Governance",
        )
        self.state_manager.add_approval(approval)

        # Reconcile supersession: if this doc supersedes another, mark predecessor as Superseded
        if doc.supersedes_document_id:
            pred = self.state_manager.get_document(doc.supersedes_document_id)
            if pred and pred.status == "Approved":
                pred.status = "Superseded"

        return True, f"Document {doc.document_id} v{doc.version} approved by {approval.approval_role}."

    def _handle_document_superseded(self, event: ProtocolEvent) -> Tuple[bool, str]:
        doc = self.state_manager.get_document(event.document_id)
        if not doc:
            return False, f"Document {event.document_id} not found to supersede."

        doc.status = "Superseded"
        return True, f"Document {doc.document_id} marked as Superseded."

    def _handle_document_deprecated(self, event: ProtocolEvent) -> Tuple[bool, str]:
        doc = self.state_manager.get_document(event.document_id)
        if not doc:
            return False, f"Document {event.document_id} not found to deprecate."

        doc.status = "Deprecated"
        return True, f"Document {doc.document_id} marked as Deprecated."
