"""Hospital Protocol Authoritative-Version Resolver | Clinical Shift Assistant.

A clean, direct, and distraction-free clinical decision support tool for hospital shift staff.
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
    page_title="Hospital Protocol Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
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

    retriever = CandidateRetriever(state.get_all_documents())
    baseline = BaselineRetriever(retriever)
    resolver = AuthoritativeResolver(retriever, state)
    rag = GroundedProtocolRAG(loader.citations_by_doc)
    processor = EventProcessor(state)

    return loader, state, retriever, baseline, resolver, rag, processor


loader, state, retriever, baseline, resolver, rag, processor = load_system()

# -----------------------------------------------------------------------------
# SIDEBAR: Shift Identity
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
st.sidebar.markdown(f"**Station:** Inpatient Ward 4B")
st.sidebar.markdown(f"**Approved Protocols:** {len([d for d in state.documents.values() if d.status == 'Approved'])}")
st.sidebar.caption("Always consult attending physician if patient condition deviates from clinical protocol standards.")

# -----------------------------------------------------------------------------
# MAIN INTERFACE: Search & Answer
# -----------------------------------------------------------------------------
st.title("🏥 Hospital Protocol Assistant")
st.caption(f"Active Session: **{active_shift}** | Clearance: **{user_role}**")

# Quick Buttons for common clinical questions
st.markdown("**Quick Clinical Questions:**")
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
    "Search protocol or ask procedure question:",
    value=preset_q or "What is the procedure for inpatient medication administration and five rights verification?",
    placeholder="e.g. What is the procedure for inpatient medication administration?",
)

if query_input:
    res = resolver.resolve(query_input, user_role=user_role)
    ans = rag.answer_query(query_input, user_role, res)

    # 1. Access Denied Case
    if res.status == "ACCESS_DENIED":
        st.error("⛔ **ACCESS RESTRICTED: Role Not Authorized**")
        st.markdown(
            f"Your current role (**{user_role}**) does not have permission to view this clinical protocol.\n\n"
            f"*Reason:* {res.message}"
        )

    # 2. Ambiguous Case
    elif res.status == "AMBIGUOUS_HITL":
        st.warning("⚠️ **Conflicting Approved Protocols Detected — Escalated to Governance**")
        st.markdown(
            f"{res.ambiguity_reason}\n\n"
            f"*Safety Guard:* This question has been queued for Clinical Governance Committee review. Please consult your attending physician."
        )

    # 3. Success Case: Show ONLY the useful clinical information
    elif res.status == "SUCCESS" and res.selected_document:
        doc = res.selected_document

        st.success(f"✅ **CURRENT APPROVED CLINICAL PROTOCOL: {doc.title} (v{doc.version})**")

        # Metadata in clean text
        st.markdown(
            f"📁 **Department:** {doc.department} &nbsp;|&nbsp; "
            f"👤 **Official Owner:** {doc.owner_id} &nbsp;|&nbsp; "
            f"📅 **Effective Date:** {doc.effective_from} &nbsp;|&nbsp; "
            f"🛡️ **Status:** Approved"
        )

        # The core clinical instruction the user actually needs
        st.info(f"📋 **Clinical Guidance:**\n\n{ans.answer}")

        # Exact Citation
        st.markdown(f"**Verified Citation:** `{ans.cited_section or doc.title}` *(Document ID: {doc.document_id})*")

st.divider()

# -----------------------------------------------------------------------------
# SECONDARY TOOL: Why Standard Search Fails (Comparison)
# -----------------------------------------------------------------------------
with st.expander("⚖️ Compare with Standard Search (Why Standard Search Fails)"):
    st.caption("Standard search ranks by keyword similarity alone and frequently picks unapproved drafts.")
    
    comp_q = st.selectbox(
        "Select a test scenario:",
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
        st.markdown("##### ❌ Standard Search (Picks Draft / Unsafe)")
        if b_d:
            st.error(f"**{b_d.title} v{b_d.version}** ({b_d.status})")
            st.write(b_ans_text)
    
    with c_right:
        st.markdown("##### ✅ Authoritative Resolver (Safe & Approved)")
        if r_r.status == "ACCESS_DENIED":
            st.error(f"⛔ **ACCESS DENIED** (Protected from role '{selected_role}')")
        elif r_r.selected_document:
            st.success(f"**{r_r.selected_document.title} v{r_r.selected_document.version}** (Approved)")
            st.write(r_ans_data.answer)
