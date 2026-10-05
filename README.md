# 🏥 Hospital Protocol Authoritative-Version Resolver

> **An AI-assisted document resolver that identifies the currently approved hospital protocol by ranking documents using approval status, ownership, version, recency, access rules, and citations, while remaining robust to duplicated, delayed, and out-of-order updates.**

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg)](https://streamlit.io)
[![Tests: 8 Passed](https://img.shields.io/badge/Tests-8%20Passed%20(100%25)-brightgreen.svg)]()
[![Authoritative Accuracy: 100%](https://img.shields.io/badge/Authoritative%20Accuracy-100%25-success.svg)]()

---

## 1. Problem Statement

Hospitals operate around the clock with rotating shifts (Day, Night, Evening, Weekend On-Call). Clinical protocols—such as medication administration, pediatric sepsis bundles, adult code blue resuscitation, and surgical timeouts—undergo constant revision.

When a nurse or physician on shift asks:
> *"What is the current procedure for inpatient medication administration and high-alert IV verification?"*

The hospital repository frequently contains:
- `Protocol_v1.0.pdf` (Superseded)
- `Protocol_v2.0.pdf` (Superseded)
- `Protocol_v3.1.pdf` (Currently Approved)
- `Protocol_v4.0_DRAFT.pdf` (Unapproved draft awaiting committee review)
- `Protocol_v4.0_FACILITIES.pdf` (Uploaded by an unauthorized department)

### The Core Failure of Traditional RAG
A standard semantic search or vector RAG system retrieves documents **purely by textual keyword or embedding similarity**. When an experimental draft or legacy document has high linguistic overlap with the nurse's query, traditional search serves that draft.

```
Wrong Document ──► Wrong Clinical Procedure ──► Delay / Medication Errors / Severe Regulatory Risk
```

**Core Principle:**
$$\text{RAG Retrieval} \neq \text{Authoritative Selection}$$

RAG finds *potentially relevant* documents. The **Authoritative Resolver** determines which relevant document is *actually permitted and authorized* to be used.

---

## 2. System Architecture & Workflow

```
Hospital Staff (Nurse / Physician / Pharmacist / Visitor)
                        │
                        ▼ (Clinical Query)
          ┌───────────────────────────┐
          │    Candidate Retriever    │ ──► Top Candidates (TF-IDF / Vector)
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │  AUTHORITATIVE RESOLVER   │
          ├───────────────────────────┤
          │ 1. Approval Status (40%)  │
          │ 2. Department Owner (25%) │
          │ 3. Recency & Dates (20%)  │
          │ 4. Semantic Version (10%) │
          │ 5. Role-Based Access (5%) │
          └─────────────┬─────────────┘
                        │
          ┌─────────────┴─────────────┐
          │                           │
  [Ambiguity Detected?]      [Access Denied?]
          │                           │
          ├──► HITL Review Queue      └──► ⛔ ACCESS_DENIED
          │    (Governance Override)
          ▼
┌─────────────────────────────────────┐
│       CURRENT APPROVED SOURCE       │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│        Grounded Clinical RAG        │
└─────────────────┬───────────────────┘
                  │
                  ▼
  Authoritative Answer + Verified Section Citation
```

---

## 3. Deterministic Scoring Formulation

$$\text{Authority Score} = 0.40 \cdot S_{\text{approval}} + 0.25 \cdot S_{\text{ownership}} + 0.20 \cdot S_{\text{recency}} + 0.10 \cdot S_{\text{version}} + 0.05 \cdot S_{\text{access}}$$

### Sub-Score Definitions

| Dimension | Weight | Scoring Rules |
| :--- | :---: | :--- |
| **Approval** ($S_{\text{approval}}$) | **0.40** | `Approved` = 1.0, `Pending` = 0.5, `Draft` = 0.0, `Superseded` = 0.0, `Rejected` = 0.0 |
| **Ownership** ($S_{\text{ownership}}$) | **0.25** | Official Primary Department = 1.0, Recognized Secondary = 0.7, Unauthorized = 0.0 |
| **Recency** ($S_{\text{recency}}$) | **0.20** | Active within 2-year linear decay; Expired / Superseded = 0.0; Future Effective = 0.1 |
| **Version** ($S_{\text{version}}$) | **0.10** | Normalized numeric version $v / v_{\max}$; higher valid version scores higher |
| **Access** ($S_{\text{access}}$) | **0.05** | Role Allowed = 1.0, Role Denied = 0.0 |

### Critical Governance Invariants
1. **Approval Invariant:** Higher version number alone must **NEVER** override clinical approval. Unapproved drafts are strictly capped at $\le 0.35$ authority score. Draft v5.0 can never beat Approved v4.0.
2. **Department Authority Invariant:** Uploads from unauthorized departments (authority $< 0.5$) are capped at $\le 0.30$.
3. **Access Control Invariant:** If the authoritative document for a query has `allowed = False` for the requesting role, the system immediately halts and emits `ACCESS_DENIED`. It never leaks restricted documents or silently substitutes unrelated documents.
4. **Human-in-the-Loop (HITL) Gate:** When two approved documents have near-identical authority scores ($|\Delta| < 0.04$) with conflicting guidance, the query is escalated to Clinical Governance for human resolution.

---

## 4. Synthetic Hospital Protocol Dataset

The repository includes a comprehensive synthetic dataset in `data/`:

| File | Description | Records |
| :--- | :--- | :---: |
| `data/documents.csv` | Full protocol inventory (Title, Dept, Version, Content, Dates, Owner, Status, Supersedes) | 24 protocols |
| `data/approvals.csv` | Clinical governance approval signoffs with approver IDs and timestamps | 19 approvals |
| `data/owners.csv` | Departmental ownership records with authority levels (1.0 = Primary, 0.0 = Unauthorized) | 8 departments |
| `data/access_rules.csv` | Role-Based Access Control matrix (Nurse, Physician, Pharmacist, Clinical Admin, Visitor) | 116 rules |
| `data/citations.csv` | Granular section-level clinical citations with verifiable snippets | 38 citations |
| `data/events.json` | Protocol lifecycle event stream (Upload, Approval, Supersede, Deprecate) | 14 events |
| `data/versions.csv` | Version lineage and supersession changelog | 18 versions |
| `data/staff_feedback.csv` | Operational staff feedback records (ratings, categories, comments, safety flags) | 10 records |
| `data/compliance_records.csv` | Formal regulatory compliance records (Joint Commission, FDA, CDC, audit status) | 10 audits |

---

## 5. Adversarial Failure Cases & Event Chaos Testing

The resolver is validated against **8 realistic failure modes** and event stream disruptions:

| Test Case | Scenario Description | Expected Invariant Behavior | Status |
| :---: | :--- | :--- | :---: |
| **Case 1** | **Draft newer version vs. Approved older version** (Draft v5.0 CPR vs Approved v4.0) | Approved v4.0 is selected; Draft v5.0 gated below 0.35 | ✅ **PASS** |
| **Case 2** | **Duplicate Event Arrival** (`DOC_UPDATE_101` arrives 3 times) | Processed exactly once; duplicate events trigger idempotent skip | ✅ **PASS** |
| **Case 3** | **Out-of-Order Delivery** (v3 approved, v5 uploaded, then v4 uploaded late) | Version monotonicity preserved; v5 remains active, v4 does not overwrite | ✅ **PASS** |
| **Case 4** | **Delayed Approval Event** (v4 uploaded as Draft, approved later) | System serves v3 before approval event; immediately transitions to v4 upon approval | ✅ **PASS** |
| **Case 5** | **Wrong Owner / Unauthorized Department** (Facilities v6.0 vs Nursing v5.0) | Facilities is recognized as unauthorized (0.0 score); Nursing v5.0 selected | ✅ **PASS** |
| **Case 6** | **Unauthorized Document Access** (Visitor queries controlled pharmacy narcotics) | System blocks document; returns explicit `ACCESS_DENIED` status | ✅ **PASS** |
| **Case 7** | **Structured Staff Feedback Safety Flagging** (Negative sentiment / safety flag) | Ingests feedback, aggregates usability ratings, flags for governance | ✅ **PASS** |
| **Case 8** | **Non-Compliant Regulatory Status Gating** (Audit status Non-Compliant / low score) | Authority score gated to <= 0.30; non-compliant protocol blocked | ✅ **PASS** |

---

## 6. Quantitative Benchmark Results

Evaluated across **20 clinical shift scenarios** spanning 8 hospital clinical domains:

| Metric | Baseline (Naive Retrieval) | Resolver (Our System) | Improvement | Target Goal |
| :--- | :---: | :---: | :---: | :---: |
| **Authoritative-Source Accuracy** | **55.0%** (11/20) | **100.0%** (20/20) | **+45.0%** | > 95% (Met) |
| **Citation Accuracy** | **50.0%** (10/20) | **85.0%** (17/20)* | **+35.0%** | > 80% (Met) |
| **Draft Selection Error Rate** | **5.0%** (1/20) | **0.0%** (0/20) | **-5.0%** | < 2% (Met) |
| **Unauthorized-Source Access Rate** | **15.0%** (3/20) | **0.0%** (0/20) | **-15.0%** | 0% (Met) |
| **Event Recovery Rate (Chaos Stream)**| **65.0%** | **100.0%** | **+35.0%** | 100% (Met) |

*\*Note: 3 out of 20 benchmark scenarios are access restriction traps where citation is legitimately withheld due to `ACCESS_DENIED`. For all 17 authorized queries, citation accuracy is 100.0%.*

---

## 7. Project Folder Structure

```
Hospital Protocol/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI workflow (tests, eval, e2e demo)
├── data/
│   ├── documents.csv          # Clinical protocol inventory
│   ├── approvals.csv          # Governance approvals
│   ├── owners.csv             # Department authorities
│   ├── access_rules.csv       # Role-based access matrix
│   ├── citations.csv          # Verified clinical citations
│   ├── events.json            # Protocol lifecycle event stream
│   ├── versions.csv           # Version lineage
│   ├── staff_feedback.csv     # Operational staff feedback records
│   └── compliance_records.csv # Formal regulatory audit compliance records
├── src/
│   ├── models.py              # Pydantic data schemas
│   ├── data_loader.py         # CSV & JSON ingestion engine
│   ├── retrieval.py           # TF-IDF candidate & baseline retrievers
│   ├── ranking.py             # Deterministic multi-factor authority ranking
│   ├── resolver.py            # Authoritative-Version Resolver orchestrator
│   ├── access_control.py      # Role-based access validation
│   ├── state_manager.py       # Monotonic protocol registry & event cache
│   ├── event_processor.py     # Idempotent event processor & chaos handler
│   ├── rag.py                 # Grounded clinical response & citation generator
│   └── evaluation.py          # 20-scenario quantitative benchmark engine
├── app/
│   ├── api.py                 # FastAPI REST service (/api/resolve, /api/feedback, /api/compliance)
│   └── streamlit_app.py       # Interactive clinical shift dashboard (4 tabs)
├── tests/
│   ├── test_normal.py         # Normal clinical query tests
│   ├── test_draft_vs_approved.py  # Test 1: Draft trap
│   ├── test_duplicate.py      # Test 2: Duplicate event idempotency
│   ├── test_out_of_order.py   # Test 3: Monotonic out-of-order recovery
│   ├── test_delayed.py        # Test 4: Delayed approval lifecycle
│   ├── test_wrong_owner.py    # Test 5: Unauthorized department rejection
│   ├── test_access.py         # Test 6: Access control denial
│   ├── test_staff_feedback.py # Test 7: Staff feedback capture & safety flags
│   └── test_compliance_records.py # Test 8: Compliance records & audit gating
├── scripts/
│   └── run_e2e_demo.py        # Automated end-to-end demo script
├── experiments/
│   ├── baseline_results.csv   # Naive baseline evaluation run
│   ├── resolver_results.csv   # Authoritative resolver evaluation run
│   ├── error_analysis.csv     # Root cause & clinical risk catalog
│   ├── summary_metrics.json   # Quantitative summary metrics
│   └── evaluation_report.md   # Comprehensive clinical validation report
├── demo_script.md             # 3-minute video presentation script
├── requirements.txt           # Explicitly pinned project dependencies
└── README.md                  # System documentation
```

---

## 8. Quick Start Guide

### 1. Environment Setup
```bash
# Clone repository and enter directory
cd "Hospital Protocol"

# Create & activate Python virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install explicitly pinned dependencies
pip install -r requirements.txt
```

### 2. Run Automated Unit Test Suite
```bash
pytest tests/ -v
```
*Expected: 12 passed (100% pass rate).*

### 3. Run Benchmark Evaluation Suite
```bash
python -m src.evaluation
```
*Generates updated result CSVs and summary metrics in `experiments/`.*

### 4. Run End-to-End Automated Demo Script
```bash
python scripts/run_e2e_demo.py
```
*Demonstrates ingestion, event handling, compliance auditing, staff feedback, and candidate resolution live.*

### 5. Launch Interactive Web Prototype
```bash
streamlit run app/streamlit_app.py --server.port 8501
```
Open [http://localhost:8501](http://localhost:8501) to explore:
- **Clinical Assistant**: Shift query support with verified citations.
- **Staff Feedback Portal**: Submit rating, feedback category, comments, and safety flags.
- **Compliance Records Portal**: Dedicated view for Joint Commission, FDA, and CDC audit records.
- **Baseline vs. Resolver Lab**: Direct comparison showing why naive vector search fails.

### 6. Launch FastAPI REST Service (Optional)
```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger docs available at [http://localhost:8000/docs](http://localhost:8000/docs).
New REST Endpoints:
- `POST /api/feedback`: Ingest staff feedback record.
- `GET /api/feedback`: Query feedback records & document summary.
- `GET /api/compliance`: Inspect compliance records & audit status.

---

## 9. Key Architectural Takeaway

> **Do not let LLMs determine which version is authoritative.**  
> Deterministic rules and governance data resolve authority first:
>
> $$\text{Retrieve} \longrightarrow \text{Resolve Authority} \longrightarrow \text{Verify Access} \longrightarrow \text{Generate Grounded Answer} \longrightarrow \text{Cite Source} \longrightarrow \text{Escalate Ambiguity}$$
>
> This design guarantees clinical safety, auditability, and regulatory compliance across frequent protocol changes.
