"""Grounded RAG and Citation Module for Hospital Protocols.

Generates answers strictly from the resolved authoritative document,
extracts the relevant section, and produces structured citations.
"""

from typing import Dict, List, Optional, Tuple
import re
from src.models import Document, Citation, QueryResult, ResolutionResult, CandidateScore
from src.retrieval import CandidateRetriever


class GroundedProtocolRAG:
    def __init__(self, citations_by_doc: Dict[str, List[Citation]]):
        self.citations_by_doc = citations_by_doc

    def extract_relevant_section(
        self, document: Document, query: str
    ) -> Tuple[str, str, str]:
        """Extracts the most relevant section from the document content or citations."""
        doc_citations = self.citations_by_doc.get(document.document_id, [])

        if doc_citations:
            # Score each citation snippet against query terms
            query_words = set(re.findall(r"\w+", query.lower()))
            best_cit = doc_citations[0]
            best_overlap = -1

            for cit in doc_citations:
                cit_words = set(re.findall(r"\w+", f"{cit.section_title} {cit.snippet}".lower()))
                overlap = len(query_words.intersection(cit_words))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cit = cit

            return (
                best_cit.section_number,
                best_cit.section_title,
                best_cit.snippet,
            )

        # Fallback: parse sections directly from document content string
        sections = re.findall(
            r"(Section\s+\d+[^:]*:\s*([^-\n.]+)[-\s]*([^.\n]+(?:\.[^.\n]+)*))",
            document.content,
            re.IGNORECASE,
        )
        if sections:
            query_words = set(re.findall(r"\w+", query.lower()))
            best_match = sections[0]
            best_overlap = -1
            for full, title, body in sections:
                text_words = set(re.findall(r"\w+", f"{title} {body}".lower()))
                overlap = len(query_words.intersection(text_words))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = (full, title, body)
            sec_num = best_match[0].split(":")[0].strip()
            return sec_num, best_match[1].strip(), best_match[2].strip()

        return "Section 1", "General Protocol", document.content

    def generate_grounded_answer(
        self,
        document: Document,
        query: str,
    ) -> Tuple[str, str, str]:
        """Generates grounded clinical response with citation."""
        sec_num, sec_title, snippet = self.extract_relevant_section(document, query)

        answer = (
            f"According to {document.title} v{document.version}, "
            f"{sec_num} ({sec_title}): {snippet}"
        )

        citation_text = (
            f"Source: {document.title}\n"
            f"Document ID: {document.document_id}\n"
            f"Version: {document.version}\n"
            f"Status: {document.status}\n"
            f"Owner Department: {document.department}\n"
            f"Effective Date: {document.effective_from}\n"
            f"Citation: {document.document_id} ({sec_num}: {sec_title})"
        )

        cited_section = f"{sec_num}: {sec_title}"
        return answer, citation_text, cited_section

    def answer_query(
        self,
        query: str,
        user_role: str,
        resolution: ResolutionResult,
        system_type: str = "RESOLVER",
    ) -> QueryResult:
        """Constructs full QueryResult from resolution result."""
        if resolution.status == "ACCESS_DENIED":
            return QueryResult(
                query=query,
                user_role=user_role,
                system_type=system_type,
                selected_document_id=None,
                status="ACCESS_DENIED",
                answer=(
                    f"⛔ ACCESS DENIED: Role '{user_role}' does not have clinical permissions "
                    f"to access this protocol. Please contact Hospital Administration or your shift supervisor."
                ),
                citation_text="No citation available (Access Restricted)",
                candidate_scores=resolution.candidate_scores,
                hitl_required=False,
                explanation=resolution.message,
            )

        if resolution.status == "AMBIGUOUS_HITL":
            selected = resolution.selected_document
            cand_scores = resolution.candidate_scores
            return QueryResult(
                query=query,
                user_role=user_role,
                system_type=system_type,
                selected_document_id=selected.document_id if selected else None,
                selected_version=selected.version if selected else None,
                selected_title=selected.title if selected else None,
                status="AMBIGUOUS_HITL",
                answer=(
                    f"⚠️ ATTENTION: Multiple conflicting approved protocols detected for this query. "
                    f"This inquiry has been escalated to Clinical Governance for immediate human review. "
                    f"Do not proceed without attending confirmation."
                ),
                citation_text=f"Pending Review: {resolution.ambiguity_reason}",
                candidate_scores=cand_scores,
                hitl_required=True,
                explanation=resolution.message,
            )

        if not resolution.selected_document:
            return QueryResult(
                query=query,
                user_role=user_role,
                system_type=system_type,
                selected_document_id=None,
                status=resolution.status,
                answer="No approved authoritative hospital protocol found matching your search.",
                citation_text="None",
                candidate_scores=resolution.candidate_scores,
                hitl_required=False,
                explanation=resolution.message,
            )

        doc = resolution.selected_document
        ans, cit_text, cited_sec = self.generate_grounded_answer(doc, query)

        top_cand = resolution.candidate_scores[0] if resolution.candidate_scores else None
        auth_score = top_cand.authority_score if top_cand else 0.0
        sim_score = top_cand.similarity_score if top_cand else 0.0

        return QueryResult(
            query=query,
            user_role=user_role,
            system_type=system_type,
            selected_document_id=doc.document_id,
            selected_version=doc.version,
            selected_title=doc.title,
            status="SUCCESS",
            answer=ans,
            citation_text=cit_text,
            cited_section=cited_sec,
            authority_score=auth_score,
            similarity_score=sim_score,
            candidate_scores=resolution.candidate_scores,
            hitl_required=False,
            explanation=resolution.message,
        )
