# 🎬 Three-Minute Demonstration Video Script
## Project: Hospital Protocol Authoritative-Version Resolver
**Timing Breakdown & Narration Script (Total: 3:00 Minutes)**

---

### [0:00 – 0:30] Segment 1: The Problem — Shift Handoffs & Version Chaos
**Visual:**
- Camera/Screen displays the Hospital Shift Control panel on the Streamlit app.
- Show multiple versions of the same protocol existing in the database:
  - `DOC-MED-001` (v1.0 - Superseded)
  - `DOC-MED-002` (v2.0 - Superseded)
  - `DOC-MED-003` (v3.0 - Superseded)
  - `DOC-MED-004` (v3.1 - Approved)
  - `DOC-MED-005` (v4.0 - Draft)
  - `DOC-MED-006` (v4.0 - Facilities Department / Wrong Owner)

**Narrator Script:**
> *"Imagine a nurse starts a critical night shift in the intensive care unit and searches: 'What is the current procedure for inpatient high-alert medication administration?' In a real hospital, protocols change frequently across rotating shifts. The system contains outdated versions, experimental drafts awaiting review, and documents from unauthorized departments.*
> 
> *Standard search and RAG systems retrieve documents based on keyword or semantic similarity alone. When an unapproved draft or superseded protocol matches the user's query with high lexical overlap, standard systems serve the wrong document. That creates severe clinical delays, operational rework, and life-threatening patient risk. We need a system that can answer: 'Which document is actually authoritative right now?'"*

---

### [0:30 – 1:00] Segment 2: Baseline Failure Demonstration
**Visual:**
- Switch to the **"Baseline vs. Resolver Lab"** tab.
- Select **Case 1: CPR Resuscitation (Draft v5.0 Trap vs Approved v4.0)**.
- Highlight the **Naive Vector Search (Baseline)** card:
  - Selected: `DOC-CPR-003` (Draft v5.0)
  - Similarity Score: `0.5313`
  - Red Alert Box: *"🚨 CLINICAL RISK: Baseline served an unapproved draft protocol with untested dosing!"*

**Narrator Script:**
> *"Here is our Baseline retrieval system in action. When an attending physician queries for 'biphasic defibrillation shock energy and epinephrine dosing during cardiac arrest', the naive search engine picks version 5.0.*
> 
> *Why? Because version 5.0 had the highest textual similarity. But version 5.0 is an unapproved clinical draft proposing experimental drug doses! In a code blue situation, acting on an unapproved draft could lead to fatal myocardial injury. Baseline retrieval fails because relevance does not equal authority."*

---

### [1:00 – 1:45] Segment 3: The Proposed System — Deterministic Authority Resolver
**Visual:**
- Highlight the right side of the screen: **Authoritative Resolver (Our System)**.
- Show the **CURRENT APPROVED SOURCE** card:
  - Document: `DOC-CPR-002` (Adult Resuscitation & Code Blue Protocol v4.0)
  - Status: `Approved`
  - Authority Score: `0.9646`
  - Grounded Clinical Guidance & Official Citation: `Section 3: Biphasic Defibrillation (200 Joules synchronized biphasic shock)`.
- Expand the **Multi-Factor Authority Breakdown**:
  - Show scoring weights: Approval (0.40), Ownership (0.25), Recency (0.20), Version (0.10), Access (0.05).
  - Show invariant gating: Draft v5.0 authority was capped at 0.35, while Approved v4.0 earned 0.96.

**Narrator Script:**
> *"Our Authoritative-Version Resolver solves this with a deterministic, explainable multi-factor scoring function. It evaluates candidate documents across five governance dimensions:*
> 1. *Approval Status (40% weight)*
> 2. *Departmental Ownership Authority (25% weight)*
> 3. *Recency and Active Effective Dates (20% weight)*
> 4. *Semantic Version Progression (10% weight)*
> 5. *Role-Based Access Rules (5% weight)*
> 
> *Most importantly, we enforce a strict invariant: version number alone must NEVER override clinical approval. Draft v5.0's authority score is capped at 0.35, while Approved v4.0 scores 0.96. The resolver selects the approved source, grounds the answer strictly from that document, and outputs a verifiable citation to Section 3."*

---

### [1:45 – 2:20] Segment 4: Adversarial & Chaos Testing
**Visual:**
- Switch to the **"Event Chaos & Ingestion"** tab.
- Click **"Simulate Duplicate Flood"**: Show event `EVT_CHAOS_DUP_101` received 3 times; show `Idempotency Preserved: Event processed exactly once`.
- Click **"Simulate Out-of-Order"**: Show v3 approved, then v5 uploaded, then v4 arrives late; show final state remains monotonically at v5.
- Click **"Simulate Delayed Approval"**: Show queries resolve to v3 prior to approval, and transition to v4 immediately after the approval event arrives.
- Return to Query Assistant with **Role: Visitor**: Query pharmacy narcotics; show **⛔ ACCESS DENIED** card.

**Narrator Script:**
> *"In high-volume hospital IT environments, event streams fail. We subjected the resolver to adversarial chaos testing:*
> - *Duplicate Event Flood: The same update is injected three times. State changes exactly once via our idempotent event cache.*
> - *Out-of-Order Delivery: Older version 4 arrives after newer version 5. The system enforces monotonicity, preventing state downgrade.*
> - *Delayed Approvals: The system safely uses version 3 until the explicit clinical approval event arrives for version 4.*
> - *Access Control: When a visitor attempts to access controlled narcotics protocols, the resolver rejects the request with an explicit ACCESS DENIED violation, completely blocking unauthorized institutional knowledge."*

---

### [2:20 – 2:45] Segment 5: Quantitative Evaluation & Measured Results
**Visual:**
- Switch to the **"Benchmarks & Audit Analytics"** tab.
- Display the KPI Metric Cards and the 20-scenario benchmark table:
  - **Authoritative-Source Accuracy:** Baseline `55.0%` ➔ Resolver `100.0%` (+45.0% gain)
  - **Citation Accuracy:** Baseline `50.0%` ➔ Resolver `85.0%` (+35.0% gain)
  - **Draft Selection Error Rate:** Baseline `5.0%` ➔ Resolver `0.0%` (Zero draft leaks)
  - **Unauthorized Access Rate:** Baseline `15.0%` ➔ Resolver `0.0%` (Zero permission breaches)
  - **Event Recovery Rate:** `100.0%`

**Narrator Script:**
> *"We evaluated both systems across a rigorous 20-scenario clinical benchmark spanning 8 hospital departments. The measured results speak for themselves:*
> - *Authoritative selection accuracy increased from 55% in the baseline to 100% with the resolver.*
> - *Draft selection errors dropped from 5% to zero.*
> - *Unauthorized access leaks were completely eliminated from 15% down to 0%.*
> - *And the system demonstrated a 100% recovery rate across all corrupted event scenarios."*

---

### [2:45 – 3:00] Segment 6: Conclusion
**Visual:**
- Return to main Shift Assistant screen showing a successfully resolved clinical query with verified citation and green approval badge.
- Display summary architectural principle: `Retrieve ➔ Resolve Authority ➔ Verify Access ➔ Generate Grounded Answer ➔ Cite Source ➔ Escalate Ambiguity`.

**Narrator Script:**
> *"By ensuring that LLMs do not decide protocol authority, and instead grounding them in a deterministic governance resolver, we eliminate shift handoff confusion, prevent draft medication errors, and guarantee that hospital staff always practice from the current approved clinical protocol. Thank you."*
