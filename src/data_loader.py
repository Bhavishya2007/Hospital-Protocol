"""Data loader module for Hospital Protocol Authoritative-Version Resolver."""

import os
import csv
import json
from typing import Dict, List, Tuple, Optional
from src.models import Document, Approval, Owner, AccessRule, Citation, ProtocolEvent


def get_default_data_dir() -> str:
    """Returns the default data directory path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(current_dir), "data")


class DataLoader:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or get_default_data_dir()
        self.documents: List[Document] = []
        self.documents_by_id: Dict[str, Document] = {}
        self.approvals: List[Approval] = []
        self.approvals_by_id: Dict[str, Approval] = {}
        self.approvals_by_doc: Dict[str, List[Approval]] = {}
        self.owners: List[Owner] = []
        self.owners_by_id: Dict[str, Owner] = {}
        self.access_rules: List[AccessRule] = []
        self.access_map: Dict[Tuple[str, str], bool] = {}  # (doc_id, role) -> allowed
        self.citations: List[Citation] = []
        self.citations_by_doc: Dict[str, List[Citation]] = {}
        self.events: List[ProtocolEvent] = []

    def load_all(self):
        """Loads all datasets from CSV and JSON files."""
        self.load_owners()
        self.load_approvals()
        self.load_documents()
        self.load_access_rules()
        self.load_citations()
        self.load_events()
        return self

    def load_documents(self, filename: str = "documents.csv") -> List[Document]:
        filepath = os.path.join(self.data_dir, filename)
        docs = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc = Document(
                    document_id=row["document_id"].strip(),
                    title=row["title"].strip(),
                    department=row["department"].strip(),
                    document_type=row.get("document_type", "Protocol").strip(),
                    version=row["version"].strip(),
                    content=row["content"].strip(),
                    created_at=row["created_at"].strip(),
                    effective_from=row["effective_from"].strip(),
                    effective_until=row["effective_until"].strip() if row.get("effective_until") else None,
                    owner_id=row["owner_id"].strip(),
                    approval_id=row["approval_id"].strip() if row.get("approval_id") else None,
                    status=row["status"].strip(),
                    access_level=row.get("access_level", "Staff").strip(),
                    supersedes_document_id=row.get("supersedes_document_id", "").strip() or None,
                )
                docs.append(doc)
                self.documents_by_id[doc.document_id] = doc
        self.documents = docs
        return docs

    def load_approvals(self, filename: str = "approvals.csv") -> List[Approval]:
        filepath = os.path.join(self.data_dir, filename)
        approvals = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                app = Approval(
                    approval_id=row["approval_id"].strip(),
                    document_id=row["document_id"].strip(),
                    approver_id=row["approver_id"].strip(),
                    approval_status=row["approval_status"].strip(),
                    approved_at=row["approved_at"].strip(),
                    approval_role=row["approval_role"].strip(),
                )
                approvals.append(app)
                self.approvals_by_id[app.approval_id] = app
                self.approvals_by_doc.setdefault(app.document_id, []).append(app)
        self.approvals = approvals
        return approvals

    def load_owners(self, filename: str = "owners.csv") -> List[Owner]:
        filepath = os.path.join(self.data_dir, filename)
        owners = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                owner = Owner(
                    owner_id=row["owner_id"].strip(),
                    department=row["department"].strip(),
                    role=row["role"].strip(),
                    authority_level=float(row.get("authority_level", 1.0)),
                    active=row.get("active", "True").lower() in ("true", "1", "yes"),
                )
                owners.append(owner)
                self.owners_by_id[owner.owner_id] = owner
        self.owners = owners
        return owners

    def load_access_rules(self, filename: str = "access_rules.csv") -> List[AccessRule]:
        filepath = os.path.join(self.data_dir, filename)
        rules = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                allowed = row["allowed"].strip().lower() in ("true", "1", "yes")
                rule = AccessRule(
                    document_id=row["document_id"].strip(),
                    role=row["role"].strip(),
                    allowed=allowed,
                )
                rules.append(rule)
                self.access_map[(rule.document_id, rule.role)] = allowed
        self.access_rules = rules
        return rules

    def load_citations(self, filename: str = "citations.csv") -> List[Citation]:
        filepath = os.path.join(self.data_dir, filename)
        cits = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cit = Citation(
                    citation_id=row["citation_id"].strip(),
                    document_id=row["document_id"].strip(),
                    version=row["version"].strip(),
                    section_number=row["section_number"].strip(),
                    section_title=row["section_title"].strip(),
                    snippet=row["snippet"].strip(),
                )
                cits.append(cit)
                self.citations_by_doc.setdefault(cit.document_id, []).append(cit)
        self.citations = cits
        return cits

    def load_events(self, filename: str = "events.json") -> List[ProtocolEvent]:
        filepath = os.path.join(self.data_dir, filename)
        events = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            raw = json.load(f)
            for item in raw:
                event = ProtocolEvent(**item)
                events.append(event)
        self.events = events
        return events
