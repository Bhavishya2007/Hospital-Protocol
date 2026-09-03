"""Deterministic Authority Ranking Module for Hospital Protocol Authoritative-Version Resolver.

Implements the multi-factor scoring function:
    Authority Score =
        0.40 * Approval Score
      + 0.25 * Ownership Score
      + 0.20 * Recency Score
      + 0.10 * Version Score
      + 0.05 * Access Score

Enforces strict clinical governance invariants:
1. Version alone MUST NEVER override approval (Draft v5.0 cannot beat Approved v4.0).
2. Expired or superseded documents are down-weighted.
3. Unauthorized owners receive 0.0 ownership score.
4. Access denied documents are flagged and cannot be presented to unauthorized roles.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import re
from src.models import Document, Owner, Approval, CandidateScore

# Reference clinical date for shift evaluations (simulating present day in 2026)
REFERENCE_DATE = date(2026, 9, 3)

# Multi-factor weights
WEIGHT_APPROVAL = 0.40
WEIGHT_OWNERSHIP = 0.25
WEIGHT_RECENCY = 0.20
WEIGHT_VERSION = 0.10
WEIGHT_ACCESS = 0.05

# Combined ranking weights (Authority carries primary weight)
WEIGHT_COMBINED_AUTHORITY = 0.70
WEIGHT_COMBINED_SIMILARITY = 0.30


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parses date string in YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        clean = date_str.split("T")[0].strip()
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return None


def parse_semver(version_str: str) -> float:
    """Extracts numeric version representation for comparison.
    E.g. '3.1' -> 3.1, '4.0-DRAFT' -> 4.0, '2.5' -> 2.5
    """
    match = re.search(r"(\d+(?:\.\d+)?)", version_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 1.0
    return 1.0


def compute_approval_score(document: Document) -> Tuple[float, str]:
    """Computes approval score based on governance state.
    Approved = 1.0
    Pending  = 0.5
    Draft    = 0.0
    Superseded = 0.0
    Rejected = 0.0
    """
    status = document.status.strip().title()
    if status == "Approved":
        return 1.0, "Approved by clinical governance"
    elif status == "Pending":
        return 0.5, "Pending formal review"
    elif status == "Draft":
        return 0.0, "Draft status - not clinically approved"
    elif status == "Superseded":
        return 0.0, "Superseded by newer approved version"
    elif status == "Rejected":
        return 0.0, "Rejected by clinical review"
    return 0.0, f"Unknown status: {status}"


def compute_ownership_score(document: Document, owners_by_id: Dict[str, Owner]) -> Tuple[float, str]:
    """Computes ownership score based on departmental authority.
    Official owner = 1.0
    Recognized department = 0.7
    Unknown / unauthorized owner = 0.0
    """
    owner = owners_by_id.get(document.owner_id)
    if not owner or not owner.active:
        return 0.0, f"Unknown or inactive owner: {document.owner_id}"

    if owner.authority_level >= 1.0:
        return 1.0, f"Primary authoritative department ({owner.department})"
    elif owner.authority_level >= 0.5:
        return 0.7, f"Recognized secondary department ({owner.department})"
    else:
        return 0.0, f"Unauthorized department ({owner.department}, authority {owner.authority_level})"


def compute_recency_score(
    document: Document, ref_date: date = REFERENCE_DATE
) -> Tuple[float, str]:
    """Computes recency score based on effective_from and effective_until dates."""
    eff_from = parse_date(document.effective_from)
    eff_until = parse_date(document.effective_until)

    # Expired check
    if eff_until and eff_until < ref_date:
        return 0.0, f"Expired on {eff_until} (superseded/deprecated)"

    # Future effective check
    if eff_from and eff_from > ref_date:
        return 0.1, f"Future effective date ({eff_from}) - not yet active"

    # Active recency calculation
    if eff_from:
        days_elapsed = (ref_date - eff_from).days
        if days_elapsed < 0:
            return 0.1, "Future effective date"
        # Linear decay over 2 years (730 days) down to 0.4
        decay = max(0.4, 1.0 - (days_elapsed / 730.0) * 0.6)
        return round(decay, 3), f"Active since {eff_from} ({days_elapsed} days ago)"

    return 0.5, "No effective date specified"


def compute_version_score(
    document: Document, max_version: float = 5.0
) -> Tuple[float, str]:
    """Computes normalized version score (0.0 to 1.0)."""
    ver_num = parse_semver(document.version)
    normalized = min(1.0, max(0.1, ver_num / max(max_version, 1.0)))
    return round(normalized, 3), f"Version {document.version} (num: {ver_num})"


def rank_candidates(
    candidates: List[Tuple[Document, float]],
    owners_by_id: Dict[str, Owner],
    access_map: Dict[Tuple[str, str], bool],
    user_role: str,
    ref_date: date = REFERENCE_DATE,
) -> List[CandidateScore]:
    """Evaluates and ranks all candidates using the deterministic multi-factor function."""
    if not candidates:
        return []

    # Noise rejection: Filter out candidates with negligible similarity if top candidate is strong
    top_sim = max((s for _, s in candidates), default=0.0)
    if top_sim >= 0.10:
        candidates = [c for c in candidates if c[1] >= 0.05 and c[1] >= top_sim * 0.20]

    if not candidates:
        return []

    # Find maximum version across candidates for normalization
    max_ver = max((parse_semver(doc.version) for doc, _ in candidates), default=1.0)

    scored_candidates: List[CandidateScore] = []

    for doc, sim_score in candidates:
        app_score, app_desc = compute_approval_score(doc)
        own_score, own_desc = compute_ownership_score(doc, owners_by_id)
        rec_score, rec_desc = compute_recency_score(doc, ref_date)
        ver_score, ver_desc = compute_version_score(doc, max_ver)

        # Access check
        is_allowed = access_map.get((doc.document_id, user_role), True)
        acc_score = 1.0 if is_allowed else 0.0
        acc_desc = "Role access granted" if is_allowed else f"Access denied for role {user_role}"

        # Raw authority calculation
        raw_authority = (
            WEIGHT_APPROVAL * app_score
            + WEIGHT_OWNERSHIP * own_score
            + WEIGHT_RECENCY * rec_score
            + WEIGHT_VERSION * ver_score
            + WEIGHT_ACCESS * acc_score
        )

        # CRITICAL INVARIANT: Draft or Superseded must never beat an approved document!
        # If document is not approved, cap authority score strictly at 0.35.
        if doc.status.strip().title() != "Approved":
            authority_score = min(raw_authority, 0.35)
            authority_desc = f"GATED (non-approved status '{doc.status}' caps score to {authority_score:.2f})"
        elif own_score == 0.0:
            authority_score = min(raw_authority, 0.30)
            authority_desc = f"GATED (unauthorized owner '{doc.owner_id}')"
        else:
            authority_score = round(raw_authority, 4)
            authority_desc = f"Calculated: {authority_score:.3f}"

        if not is_allowed:
            authority_desc += f" [ACCESS RESTRICTED for {user_role}]"

        # Combined score blending relevance similarity with authority
        if doc.status.strip().title() != "Approved":
            # Penalize unapproved combined score so it never outranks valid approved source
            combined_score = round(0.20 * sim_score + 0.80 * authority_score, 4)
        else:
            combined_score = round(
                WEIGHT_COMBINED_SIMILARITY * sim_score
                + WEIGHT_COMBINED_AUTHORITY * authority_score,
                4,
            )

        explanation = (
            f"Approval: {app_score} ({app_desc}) | "
            f"Ownership: {own_score} ({own_desc}) | "
            f"Recency: {rec_score} ({rec_desc}) | "
            f"Version: {ver_score} ({ver_desc}) | "
            f"Access: {acc_score} ({acc_desc}) | "
            f"Authority: {authority_desc}"
        )

        scored = CandidateScore(
            document_id=doc.document_id,
            title=doc.title,
            version=doc.version,
            department=doc.department,
            status=doc.status,
            owner_id=doc.owner_id,
            effective_from=doc.effective_from,
            effective_until=doc.effective_until,
            similarity_score=round(sim_score, 4),
            approval_score=round(app_score, 3),
            ownership_score=round(own_score, 3),
            recency_score=round(rec_score, 3),
            version_score=round(ver_score, 3),
            access_score=round(acc_score, 3),
            authority_score=round(authority_score, 4),
            combined_score=round(combined_score, 4),
            is_access_allowed=is_allowed,
            explanation=explanation,
        )
        scored_candidates.append(scored)

    # Sort descending by combined_score, then authority_score, then similarity_score
    scored_candidates.sort(
        key=lambda c: (c.combined_score, c.authority_score, c.similarity_score),
        reverse=True,
    )

    # Assign ranks and mark authoritative candidate
    for idx, cand in enumerate(scored_candidates):
        cand.rank = idx + 1

    if scored_candidates and scored_candidates[0].authority_score >= 0.70:
        scored_candidates[0].is_authoritative = True

    return scored_candidates
