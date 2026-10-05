"""Hospital Protocol Authoritative-Version Resolver | Clinical Shift Assistant.

A modern, high-contrast, state-of-the-art clinical governance decision support tool.
Immediately identifies the currently approved authoritative protocol and verified procedure.
"""

import sys
import os
import time
import pandas as pd
import streamlit as st

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever, BaselineRetriever
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor
from src.resolver import AuthoritativeResolver
from src.rag import GroundedProtocolRAG

# Streamlit Page Setup
st.set_page_config(
    page_title="Hospital Protocol Authoritative Resolver",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-End Modern CSS (Google Fonts, Glassmorphism, Neon Badges, Gradient Cards)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Top Hero Header */
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px 30px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        color: #ffffff;
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
        margin: 0;
    }
    .hero-badge {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* Selected Authoritative Protocol Card */
    .card-selected {
        background: linear-gradient(135deg, #022c22 0%, #064e3b 50%, #022c22 100%);
        border: 2px solid #10b981;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 15px 35px -5px rgba(16, 185, 129, 0.3);
        position: relative;
        overflow: hidden;
    }
    .badge-selected {
        background: #10b981;
        color: #022c22;
        font-weight: 800;
        font-size: 0.85rem;
        padding: 6px 14px;
        border-radius: 20px;
        letter-spacing: 0.5px;
        display: inline-block;
        margin-bottom: 12px;
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.5);
    }
    .selected-title {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0 0 10px 0;
    }
    .selected-meta {
        color: #a7f3d0;
        font-size: 0.95rem;
        margin-bottom: 16px;
    }
    .selected-guidance-box {
        background: rgba(0, 0, 0, 0.4);
        border-left: 4px solid #34d399;
        border-radius: 8px;
        padding: 16px 20px;
        color: #ecfdf5;
        font-size: 1.05rem;
        line-height: 1.6;
        margin-top: 14px;
    }

    /* Non-Selected Candidates Cards */
    .card-nonselected {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .card-nonselected:hover {
        border-color: #64748b;
        transform: translateY(-1px);
    }
    .badge-superseded {
        background: #475569;
        color: #cbd5e1;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 12px;
    }
    .badge-draft {
        background: #9a3412;
        color: #ffedd5;
        border: 1px solid #f97316;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 12px;
    }
    .badge-unauthorized {
        background: #991b1b;
        color: #fee2e2;
        border: 1px solid #ef4444;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 12px;
    }

    /* Stat Pills */
    .stat-pill {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #e2e8f0;
        padding: 4px 10px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.85rem;
    }

    /* Comparison Lab Cards */
    .comp-card-baseline {
        background: linear-gradient(135deg, #450a0a 0%, #7f1d1d 100%);
        border: 2px solid #f87171;
        border-radius: 14px;
        padding: 20px;
        color: #fef2f2;
    }
    .comp-card-resolver {
        background: linear-gradient(135deg, #022c22 0%, #065f46 100%);
        border: 2px solid #34d399;
        border-radius: 14px;
        padding: 20px;
        color: #ecfdf5;
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_system():
    loader = DataLoader()
    loader.load_all()

    state = ProtocolStateManager()
    for doc in loader.documents:
        state.add_document(doc)
    for app_rec in loader.approvals:
        state.add_approval(app_rec)
    for owner in loader.owners:
        state.add_owner(owner)
    for rule in loader.access_rules:
        state.set_access(rule.document_id, rule.role, rule.allowed)
    for fb in loader.staff_feedback:
        state.add_staff_feedback(fb)
    for doc_id, comp in loader.compliance_by_doc.items():
        state.set_compliance_record(comp)

    retriever = CandidateRetriever(state.get_all_documents())
    baseline = BaselineRetriever(retriever)
    resolver = AuthoritativeResolver(retriever, state)
    rag = GroundedProtocolRAG(loader.citations_by_doc)
    processor = EventProcessor(state)

    return loader, state, retriever, baseline, resolver, rag, processor


loader, state, retriever, baseline, resolver, rag, processor = load_system()

# -----------------------------------------------------------------------------
# SIDEBAR: Shift Identity & Station Control
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 Clinical Station")
user_role = st.sidebar.selectbox(
    "My Clinical Role",
    ["Nurse", "Physician", "Pharmacist", "Clinical_Admin", "Visitor"],
    index=0,
)

active_shift = st.sidebar.selectbox(
    "Current Shift",
    [
        "Night Shift (23:00 - 07:00)",
        "Day Shift (07:00 - 15:00)",
        "Evening Shift (15:00 - 23:00)",
        "Weekend On-Call",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown(f"**Station Location:** Inpatient Ward 4B")
st.sidebar.markdown(f"**Active Protocols:** {len(state.documents)} Total")
st.sidebar.markdown(f"**Approved Standards:** {len([d for d in state.documents.values() if d.status == 'Approved'])}")
st.sidebar.caption("Deterministic governance engine enforces approval, department ownership, recency, and RBAC security.")

# -----------------------------------------------------------------------------
# HERO HEADER
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="hero-header">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h1 class="hero-title">🏥 Hospital Protocol Authoritative Resolver</h1>
                <p class="hero-subtitle">Deterministic Governance & Decision Support for Shift Workflows</p>
            </div>
            <div>
                <span class="hero-badge">SHIFT: {active_shift}</span> &nbsp;
                <span class="hero-badge" style="background:rgba(16,185,129,0.2); color:#34d399; border-color:rgba(16,185,129,0.4);">CLEARANCE: {user_role}</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# MAIN INTERFACE TABS
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🏥 Authoritative Clinical Search",
    "💬 Staff Feedback Portal",
    "📊 Compliance Audit Records",
    "⚖️ Standard Search vs. Resolver Lab"
])

# -----------------------------------------------------------------------------
# TAB 1: Clinical Assistant & Resolver
# -----------------------------------------------------------------------------
with tab1:
    st.markdown("##### ⚡ Quick Shift Scenarios:")
    c1, c2, c3, c4 = st.columns(4)
    preset_q = None

    if c1.button("💊 Medication 5 Rights", use_container_width=True):
        preset_q = "What is the procedure for inpatient medication administration and five rights verification?"
    if c2.button("❤️ Adult Code Blue CPR", use_container_width=True):
        preset_q = "What is the biphasic defibrillation shock energy and epinephrine dosing during adult cardiac arrest?"
    if c3.button("🧼 C. Diff Contact PPE", use_container_width=True):
        preset_q = "What are the enhanced contact isolation PPE requirements for C. difficile and enteric pathogens?"
    if c4.button("🔒 Narcotics Disposal", use_container_width=True):
        preset_q = "How do I access and dispose of controlled substance narcotics in the medication room?"

    query_input = st.text_input(
        "Enter clinical question or protocol procedure request:",
        value=preset_q or "What is the procedure for inpatient medication administration and five rights verification?",
        placeholder="e.g. What is the procedure for inpatient medication administration?",
    )

    if query_input:
        res = resolver.resolve(query_input, user_role=user_role, top_k=6)
        ans = rag.answer_query(query_input, user_role, res)

        # 1. Access Denied Case
        if res.status == "ACCESS_DENIED":
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #450a0a 0%, #7f1d1d 100%); border:2px solid #ef4444; border-radius:14px; padding:20px; color:#fef2f2; margin-top:15px;">
                    <span style="background:#ef4444; color:#ffffff; font-weight:800; padding:4px 12px; border-radius:12px; font-size:0.8rem;">⛔ ACCESS DENIED</span>
                    <h3 style="margin-top:10px; color:#ffffff;">Access Restricted for Role '{user_role}'</h3>
                    <p style="color:#fca5a5; font-size:1rem;">{res.message}</p>
                    <small style="color:#f87171;">Governance Rule: Restricted protocols are strictly blocked from unauthorized role clearance.</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 2. Ambiguous Case (HITL Trigger)
        elif res.status == "AMBIGUOUS_HITL":
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg, #451a03 0%, #78350f 100%); border:2px solid #f97316; border-radius:14px; padding:20px; color:#fff7ed; margin-top:15px;">
                    <span style="background:#f97316; color:#ffffff; font-weight:800; padding:4px 12px; border-radius:12px; font-size:0.8rem;">⚠️ AMBIGUITY DETECTED - ESCALATED TO GOVERNANCE</span>
                    <h3 style="margin-top:10px; color:#ffffff;">Conflicting Approved Protocols Detected</h3>
                    <p style="color:#fdba74; font-size:1rem;">{res.ambiguity_reason}</p>
                    <small style="color:#fb923c;">Safety Invariant: Equal-authority conflicts escalate automatically to Clinical Governance for human resolution.</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 3. Success Case: Distinct High-Contrast Selected Card
        elif res.status == "SUCCESS" and res.selected_document:
            selected_doc = res.selected_document
            comp_rec = state.get_compliance_record(selected_doc.document_id)

            comp_badge = f"🏛️ Audit: {comp_rec.audit_status} ({comp_rec.regulatory_body})" if comp_rec else "🏛️ Regulatory Verified"

            st.markdown(
                f"""
                <div class="card-selected">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="badge-selected">🟢 SELECTED AUTHORITATIVE PROTOCOL</span>
                        <span style="color:#a7f3d0; font-size:0.9rem; font-weight:600;">{comp_badge}</span>
                    </div>
                    <h2 class="selected-title">{selected_doc.title} (v{selected_doc.version})</h2>
                    <div class="selected-meta">
                        📁 <strong>Department:</strong> {selected_doc.department} &nbsp;|&nbsp;
                        👤 <strong>Official Owner:</strong> {selected_doc.owner_id} &nbsp;|&nbsp;
                        📅 <strong>Effective:</strong> {selected_doc.effective_from} &nbsp;|&nbsp;
                        🛡️ <strong>Status:</strong> <span style="color:#34d399; font-weight:700;">APPROVED</span>
                    </div>
                    <div style="display:flex; gap:10px; margin-bottom:12px;">
                        <span class="stat-pill">Authority Score: {res.candidate_scores[0].authority_score:.4f}</span>
                        <span class="stat-pill">Similarity: {res.candidate_scores[0].similarity_score:.4f}</span>
                        <span class="stat-pill">Combined Rank: #1</span>
                    </div>
                    <div class="selected-guidance-box">
                        <strong style="color:#34d399; font-size:1.1rem;">📋 Verified Clinical Guidance:</strong><br/><br/>
                        {ans.answer}
                    </div>
                    <div style="margin-top:14px; font-size:0.95rem; color:#d1fae5;">
                        <strong>Verified Citation:</strong> <code>{ans.cited_section or selected_doc.title}</code> 
                        <span style="color:#6ee7b7; font-size:0.85rem;">(Doc ID: {selected_doc.document_id})</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # --- VISUAL DECISION MATRIX: SELECTED VS NON-SELECTED ---
            with st.expander("🔍 Governance Matrix: Selected vs. Non-Selected Candidates"):
                st.caption("Detailed candidate scoring breakdown comparing the selected authoritative protocol against lower-ranked or unapproved candidates:")

                for cand in res.candidate_scores:
                    is_selected = (cand.document_id == selected_doc.document_id)

                    if is_selected:
                        st.markdown(
                            f"""
                            <div style="border: 2px solid #10b981; background: rgba(16, 185, 129, 0.15); padding: 14px; border-radius: 10px; margin-bottom: 10px;">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <strong style="color:#34d399; font-size:1.05rem;">🟢 RANK #{cand.rank} [SELECTED AUTHORITATIVE SOURCE]: {cand.title} (v{cand.version})</strong>
                                    <span style="background:#10b981; color:#022c22; font-weight:800; font-size:0.75rem; padding:3px 10px; border-radius:10px;">SELECTED</span>
                                </div>
                                <div style="margin-top:6px; color:#e2e8f0; font-size:0.9rem;">
                                    Department: <strong>{cand.department}</strong> | Owner: <strong>{cand.owner_id}</strong> | Status: <strong style="color:#34d399;">{cand.status}</strong>
                                </div>
                                <div style="margin-top:6px; color:#94a3b8; font-size:0.85rem;">
                                    <em>{cand.explanation}</em>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        # Non-Selected candidate card with badging
                        badge_html = '<span class="badge-superseded">⚪ NOT SELECTED (SUPERSEDED)</span>'
                        if cand.status == "Draft":
                            badge_html = '<span class="badge-draft">⚠️ NOT SELECTED (GATED DRAFT - SCORE 0.35)</span>'
                        elif "unauthorized" in cand.explanation.lower():
                            badge_html = '<span class="badge-unauthorized">⛔ NOT SELECTED (UNAUTHORIZED OWNER)</span>'

                        st.markdown(
                            f"""
                            <div class="card-nonselected">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <strong style="color:#94a3b8; font-size:1rem;">RANK #{cand.rank}: {cand.title} (v{cand.version})</strong>
                                    {badge_html}
                                </div>
                                <div style="margin-top:4px; color:#cbd5e1; font-size:0.85rem;">
                                    Department: <strong>{cand.department}</strong> | Authority Score: <span style="font-family:monospace; color:#f59e0b;">{cand.authority_score:.4f}</span> | Similarity: <span style="font-family:monospace;">{cand.similarity_score:.4f}</span>
                                </div>
                                <div style="margin-top:4px; color:#64748b; font-size:0.8rem;">
                                    <em>{cand.explanation}</em>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

# -----------------------------------------------------------------------------
# TAB 2: Structured Staff Feedback Portal
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("💬 Operational Staff Feedback Portal")
    st.caption("Submit structured operational feedback directly into the protocol governance engine.")

    fb_doc_ids = list(state.documents.keys())
    sel_doc_id = st.selectbox("Select Target Protocol Document:", fb_doc_ids, index=3 if len(fb_doc_ids) > 3 else 0)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fb_category = st.selectbox("Feedback Category", ["Clarity", "Usability", "Safety", "Outdated Info", "Formatting"])
        fb_rating = st.slider("Usability & Clinical Safety Rating (1-5)", 1, 5, 5)
    with col_f2:
        fb_comment = st.text_area("Feedback Comments & Field Observations", placeholder="Provide clear observations regarding clinical protocol execution...")
        flag_safety = st.checkbox("🚩 Flag for Governance Review (Critical Clinical Risk)")

    if st.button("Submit Structured Feedback", use_container_width=True):
        if fb_comment.strip():
            from src.models import StaffFeedback
            import datetime
            new_fb = StaffFeedback(
                feedback_id=f"FB-{len(state.staff_feedback) + 1:03d}",
                document_id=sel_doc_id,
                user_role=user_role,
                shift=active_shift,
                rating=fb_rating,
                feedback_category=fb_category,
                comment=fb_comment.strip(),
                timestamp=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                sentiment_score=0.9 if fb_rating >= 4 else (0.5 if fb_rating == 3 else 0.1),
                flag_for_review=flag_safety,
            )
            state.add_staff_feedback(new_fb)
            st.success(f"Feedback entry '{new_fb.feedback_id}' successfully recorded!")
        else:
            st.warning("Please enter a comment before submitting.")

    st.divider()
    st.markdown("### 📊 Active Document Feedback Summary")
    doc_fb = state.get_feedback_for_document(sel_doc_id)
    summary = state.get_feedback_summary_for_doc(sel_doc_id)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Staff Reviews", summary["total_reviews"])
    m2.metric("Average Rating", f"{summary['avg_rating']} / 5.0")
    m3.metric("Sentiment Score", f"{summary['avg_sentiment']:.2f}")
    m4.metric("Flagged Safety Issues", summary["flagged_count"])

    if doc_fb:
        fb_df = pd.DataFrame([f.model_dump() for f in doc_fb])
        st.dataframe(fb_df[["feedback_id", "user_role", "shift", "rating", "feedback_category", "comment", "flag_for_review"]], use_container_width=True)
    else:
        st.info(f"No feedback entries recorded yet for document '{sel_doc_id}'.")

# -----------------------------------------------------------------------------
# TAB 3: Dedicated Compliance Audit Records
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("📊 Dedicated Compliance & Regulatory Audit Portal")
    st.caption("Formalized regulatory audit records tracking Joint Commission, FDA, CDC, and CMS compliance signoffs.")

    comp_records = list(state.compliance_records.values())
    total_c = len(comp_records)
    compliant_c = sum(1 for r in comp_records if r.audit_status == "Compliant")
    comp_rate = (compliant_c / total_c * 100.0) if total_c > 0 else 100.0

    cm1, cm2, cm3 = st.columns(3)
    cm1.metric("Total Regulatory Audits", total_c)
    cm2.metric("Compliant Protocols", compliant_c)
    cm3.metric("Compliance Rate", f"{comp_rate:.1f}%")

    st.divider()
    if comp_records:
        comp_df = pd.DataFrame([r.model_dump() for r in comp_records])
        st.dataframe(
            comp_df[[
                "compliance_id",
                "document_id",
                "audit_status",
                "regulatory_body",
                "compliance_score",
                "last_audit_date",
                "next_audit_due",
                "signoff_officer",
            ]],
            use_container_width=True,
        )

# -----------------------------------------------------------------------------
# TAB 4: Standard Search vs. Resolver Lab
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("⚖️ Naive Vector Search vs. Authoritative Resolver Lab")
    st.caption("Direct visual comparison demonstrating how standard semantic vector search serves dangerous unapproved drafts.")

    comp_q = st.selectbox(
        "Select an adversarial test scenario:",
        [
            "Adult CPR Resuscitation (Unapproved Draft v5.0 Trap)",
            "C. Difficile PPE (Outdated Superseded v1.0 Trap)",
            "High-Alert Medication Dual Signoff (Draft v4.0 Trap)",
            "Pharmacy Narcotics Disposal (Visitor Access Security Check)",
        ],
    )

    comp_queries = {
        "Adult CPR Resuscitation (Unapproved Draft v5.0 Trap)": (
            "What is the biphasic defibrillation shock energy and epinephrine dosing during adult cardiac arrest?",
            "Physician",
        ),
        "C. Difficile PPE (Outdated Superseded v1.0 Trap)": (
            "What are the enhanced contact isolation PPE requirements for C. difficile and enteric pathogens?",
            "Nurse",
        ),
        "High-Alert Medication Dual Signoff (Draft v4.0 Trap)": (
            "What is the dual signoff verification procedure for IV push high-alert medications like insulin and heparin?",
            "Nurse",
        ),
        "Pharmacy Narcotics Disposal (Visitor Access Security Check)": (
            "How do I access and dispose of controlled substance narcotics in the medication room?",
            "Visitor",
        ),
    }

    selected_q, selected_role = comp_queries[comp_q]

    # Baseline
    b_d, b_s, _ = baseline.search(selected_q)
    b_ans_text, _, _ = rag.generate_grounded_answer(b_d, selected_q) if b_d else ("No document found", "None", "None")

    # Resolver
    r_r = resolver.resolve(selected_q, user_role=selected_role)
    r_ans_data = rag.answer_query(selected_q, selected_role, r_r)

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown(
            f"""
            <div class="comp-card-baseline">
                <span style="background:#ef4444; color:#ffffff; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:10px;">❌ NAIVE VECTOR SEARCH</span>
                <h3 style="margin-top:8px; color:#ffffff;">Unfiltered Similarity Match</h3>
                <p style="color:#fca5a5; margin-bottom:6px;">Picks documents purely by keyword embedding similarity without approval checks.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if b_d:
            st.error(f"**Selected:** {b_d.title} (v{b_d.version}) — **Status:** {b_d.status}")
            st.write(b_ans_text)

    with c_right:
        st.markdown(
            f"""
            <div class="comp-card-resolver">
                <span style="background:#10b981; color:#022c22; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:10px;">✅ AUTHORITATIVE RESOLVER</span>
                <h3 style="margin-top:8px; color:#ffffff;">Multi-Factor Governance Selection</h3>
                <p style="color:#a7f3d0; margin-bottom:6px;">Enforces approval invariants, department ownership, recency, and access security.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if r_r.status == "ACCESS_DENIED":
            st.error(f"⛔ **ACCESS DENIED** (Protected from role '{selected_role}')")
        elif r_r.selected_document:
            st.success(f"**Selected:** {r_r.selected_document.title} (v{r_r.selected_document.version}) — **Status:** Approved")
            st.write(r_ans_data.answer)
