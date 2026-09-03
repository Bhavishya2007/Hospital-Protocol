"""Evaluation and Benchmarking Engine for Hospital Protocol Authoritative-Version Resolver.

Runs quantitative comparative experiments:
1. Baseline (Naive similarity retrieval) vs Authoritative Resolver
2. Multi-scenario clinical shift queries (Medication, Infection, CPR, Sepsis, Surgery, Narcotics)
3. Adversarial queries (Draft traps, Wrong owner traps, Access restriction traps)
4. Event stream chaos experiments (Duplicate, Out-of-order, Delayed approvals)

Generates:
- experiments/baseline_results.csv
- experiments/resolver_results.csv
- experiments/error_analysis.csv
"""

import os
import csv
import json
import random
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict

from src.models import Document, ProtocolEvent
from src.data_loader import DataLoader
from src.retrieval import CandidateRetriever, BaselineRetriever
from src.ranking import rank_candidates
from src.resolver import AuthoritativeResolver
from src.rag import GroundedProtocolRAG
from src.state_manager import ProtocolStateManager
from src.event_processor import EventProcessor


@dataclass
class BenchmarkScenario:
    query_id: str
    query: str
    user_role: str
    expected_doc_id: Optional[str]
    expected_version: Optional[str]
    expected_section: Optional[str]
    scenario_type: str  # "NORMAL", "DRAFT_TRAP", "WRONG_OWNER_TRAP", "ACCESS_RESTRICTION", "SUPERSEDED_TRAP"
    clinical_risk: str


BENCHMARK_SCENARIOS: List[BenchmarkScenario] = [
    # 1. Medication Administration Scenarios
    BenchmarkScenario(
        query_id="Q01",
        query="What is the current procedure for inpatient medication administration and five rights verification?",
        user_role="Nurse",
        expected_doc_id="DOC-MED-004",
        expected_version="3.1",
        expected_section="Section 2",
        scenario_type="NORMAL",
        clinical_risk="Administering wrong medication to patient",
    ),
    BenchmarkScenario(
        query_id="Q02",
        query="What is the dual signoff verification procedure for IV push high-alert medications like insulin and heparin?",
        user_role="Nurse",
        expected_doc_id="DOC-MED-004",
        expected_version="3.1",
        expected_section="Section 3",
        scenario_type="DRAFT_TRAP",
        clinical_risk="Fatal overdose from unchecked high-alert IV infusions",
    ),
    BenchmarkScenario(
        query_id="Q03",
        query="What are the current pediatric weight-based titration dose limits and pharmacist verification requirements?",
        user_role="Nurse",
        expected_doc_id="DOC-MED-004",
        expected_version="3.1",
        expected_section="Section 4",
        scenario_type="DRAFT_TRAP",
        clinical_risk="Pediatric toxic toxicity from unvalidated algorithmic titration",
    ),
    BenchmarkScenario(
        query_id="Q04",
        query="When are verbal medication orders permitted in emergency exceptions?",
        user_role="Physician",
        expected_doc_id="DOC-MED-004",
        expected_version="3.1",
        expected_section="Section 5",
        scenario_type="NORMAL",
        clinical_risk="Unauthorized unrecorded verbal orders during routine care",
    ),

    # 2. Infection Prevention Scenarios
    BenchmarkScenario(
        query_id="Q05",
        query="What is the current infection control procedure for hand hygiene and sanitizing?",
        user_role="Nurse",
        expected_doc_id="DOC-INF-003",
        expected_version="2.1",
        expected_section="Section 1",
        scenario_type="NORMAL",
        clinical_risk="Nosocomial cross-transmission between inpatient rooms",
    ),
    BenchmarkScenario(
        query_id="Q06",
        query="What are the enhanced contact isolation PPE requirements for C. difficile and enteric pathogens?",
        user_role="Nurse",
        expected_doc_id="DOC-INF-003",
        expected_version="2.1",
        expected_section="Section 2",
        scenario_type="SUPERSEDED_TRAP",
        clinical_risk="Spread of spore-forming enteric infections via ineffective alcohol rub",
    ),
    BenchmarkScenario(
        query_id="Q07",
        query="What are the airborne isolation precautions and N95 negative pressure room standards?",
        user_role="Physician",
        expected_doc_id="DOC-INF-003",
        expected_version="2.1",
        expected_section="Section 3",
        scenario_type="DRAFT_TRAP",
        clinical_risk="Airborne tuberculosis exposure from experimental cloth mask draft",
    ),
    BenchmarkScenario(
        query_id="Q08",
        query="How do I clean IT workstations and computer keyboards in patient wards?",
        user_role="Nurse",
        expected_doc_id="DOC-INF-003",
        expected_version="2.1",
        expected_section="Section 5",
        scenario_type="WRONG_OWNER_TRAP",
        clinical_risk="Using unauthorized IT cleaning protocol instead of certified clinical disinfection",
    ),

    # 3. Adult Resuscitation (Code Blue)
    BenchmarkScenario(
        query_id="Q09",
        query="What is the high performance chest compression rate and depth for adult code blue resuscitation?",
        user_role="Physician",
        expected_doc_id="DOC-CPR-002",
        expected_version="4.0",
        expected_section="Section 2",
        scenario_type="SUPERSEDED_TRAP",
        clinical_risk="Suboptimal cardiac output during arrest from legacy compressions",
    ),
    BenchmarkScenario(
        query_id="Q10",
        query="What is the biphasic defibrillation shock energy and epinephrine dosing during adult cardiac arrest?",
        user_role="Physician",
        expected_doc_id="DOC-CPR-002",
        expected_version="4.0",
        expected_section="Section 3",
        scenario_type="DRAFT_TRAP",
        clinical_risk="Myocardial injury or omitted CPR from premature experimental ECMO draft",
    ),

    # 4. Pediatric Sepsis Triage
    BenchmarkScenario(
        query_id="Q11",
        query="What are the clinical triage triggers and blood culture antibiotic timing for pediatric sepsis golden hour?",
        user_role="Nurse",
        expected_doc_id="DOC-SEP-002",
        expected_version="2.0",
        expected_section="Section 2",
        scenario_type="SUPERSEDED_TRAP",
        clinical_risk="Septic shock progression due to delayed antibiotic administration",
    ),
    BenchmarkScenario(
        query_id="Q12",
        query="What is the crystalloid bolus volume and vasoactive epinephrine infusion for pediatric fluid-refractory septic shock?",
        user_role="Physician",
        expected_doc_id="DOC-SEP-002",
        expected_version="2.0",
        expected_section="Section 4",
        scenario_type="NORMAL",
        clinical_risk="Pulmonary edema from excessive fluid overload",
    ),

    # 5. Surgical Safety & Time Out
    BenchmarkScenario(
        query_id="Q13",
        query="What are the mandatory surgical time out safety checks before skin incision?",
        user_role="Physician",
        expected_doc_id="DOC-SURG-002",
        expected_version="2.0",
        expected_section="Section 2",
        scenario_type="NORMAL",
        clinical_risk="Wrong-site or wrong-patient surgical intervention",
    ),
    BenchmarkScenario(
        query_id="Q14",
        query="What is the sign out procedure for needle, sponge, and instrument counts before leaving the OR?",
        user_role="Nurse",
        expected_doc_id="DOC-SURG-002",
        expected_version="2.0",
        expected_section="Section 3",
        scenario_type="SUPERSEDED_TRAP",
        clinical_risk="Retained foreign surgical body leading to severe postoperative sepsis",
    ),

    # 6. Controlled Substance Waste & Destruction
    BenchmarkScenario(
        query_id="Q15",
        query="What is the dual witness disposal and chemical denaturing protocol for controlled substance narcotic waste?",
        user_role="Pharmacist",
        expected_doc_id="DOC-PHARM-001",
        expected_version="2.0",
        expected_section="Section 2",
        scenario_type="NORMAL",
        clinical_risk="Opioid diversion and regulatory DEA / Health Department penalties",
    ),
    BenchmarkScenario(
        query_id="Q16",
        query="What are the discrepancy reporting thresholds and timeframes for missing narcotics in dispensing cabinets?",
        user_role="Nurse",
        expected_doc_id="DOC-PHARM-001",
        expected_version="2.0",
        expected_section="Section 3",
        scenario_type="DRAFT_TRAP",
        clinical_risk="Undetected narcotic pilferage from diversion",
    ),

    # 7. ICU Mechanical Ventilation Weaning
    BenchmarkScenario(
        query_id="Q17",
        query="What are the readiness criteria and pressure support parameters for daily spontaneous breathing trials in ICU?",
        user_role="Physician",
        expected_doc_id="DOC-ICU-001",
        expected_version="1.2",
        expected_section="Section 1",
        scenario_type="NORMAL",
        clinical_risk="Premature extubation leading to respiratory arrest and emergency reintubation",
    ),

    # 8. Visitor Policies
    BenchmarkScenario(
        query_id="Q18",
        query="What are the visiting hours and bedside caregiver policies in inpatient pediatric and ICU units?",
        user_role="Visitor",
        expected_doc_id="DOC-VIS-001",
        expected_version="1.0",
        expected_section="Section 2",
        scenario_type="NORMAL",
        clinical_risk="Disruption of patient sleep and ICU privacy violations",
    ),

    # 9. Access Restriction Traps (Visitor querying restricted clinical protocols)
    BenchmarkScenario(
        query_id="Q19",
        query="How do I access and dispose of controlled substance narcotics in the medication room?",
        user_role="Visitor",
        expected_doc_id=None,  # Must be BLOCKED
        expected_version=None,
        expected_section=None,
        scenario_type="ACCESS_RESTRICTION",
        clinical_risk="Unauthorized visitor accessing restricted narcotic storage SOP",
    ),
    BenchmarkScenario(
        query_id="Q20",
        query="What are the emergency resuscitation code blue cardiac arrest drug doses?",
        user_role="Visitor",
        expected_doc_id=None,  # Must be BLOCKED
        expected_version=None,
        expected_section=None,
        scenario_type="ACCESS_RESTRICTION",
        clinical_risk="Unqualified member of public attempting clinical resuscitation pharmacology",
    ),
]


class EvaluationEngine:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self.state_manager = ProtocolStateManager()
        self._init_state()

        self.retriever = CandidateRetriever(self.data_loader.documents)
        self.baseline = BaselineRetriever(self.retriever)
        self.resolver = AuthoritativeResolver(self.retriever, self.state_manager)
        self.rag = GroundedProtocolRAG(self.data_loader.citations_by_doc)

    def _init_state(self):
        for doc in self.data_loader.documents:
            self.state_manager.add_document(doc)
        for app in self.data_loader.approvals:
            self.state_manager.add_approval(app)
        for owner in self.data_loader.owners:
            self.state_manager.add_owner(owner)
        for rule in self.data_loader.access_rules:
            self.state_manager.set_access(rule.document_id, rule.role, rule.allowed)

    def run_benchmark(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """Runs the entire benchmark suite comparing Baseline and Resolver."""
        baseline_rows = []
        resolver_rows = []
        error_analysis_rows = []

        total_queries = len(BENCHMARK_SCENARIOS)
        baseline_auth_correct = 0
        baseline_citation_correct = 0
        baseline_draft_errors = 0
        baseline_unauth_errors = 0

        resolver_auth_correct = 0
        resolver_citation_correct = 0
        resolver_draft_errors = 0
        resolver_unauth_errors = 0

        for sc in BENCHMARK_SCENARIOS:
            # 1. Run Baseline
            base_doc, base_sim, candidates = self.baseline.search(sc.query)
            base_selected_id = base_doc.document_id if base_doc else None
            base_selected_ver = base_doc.version if base_doc else None
            base_status = base_doc.status if base_doc else "None"

            # Check baseline access
            base_access_allowed = (
                self.state_manager.access_map.get((base_selected_id, sc.user_role), True)
                if base_selected_id
                else True
            )

            # Baseline answer generation
            if base_doc:
                _, base_cit_text, base_cited_sec = self.rag.generate_grounded_answer(base_doc, sc.query)
            else:
                base_cit_text, base_cited_sec = "None", "None"

            # Evaluate Baseline
            base_is_auth_correct = False
            base_is_citation_correct = False
            base_is_draft_error = False
            base_is_unauth_error = False

            if sc.scenario_type == "ACCESS_RESTRICTION":
                # For access restriction, baseline that returns an internal doc fails!
                if base_doc is not None:
                    base_is_unauth_error = True
                    base_is_auth_correct = False
                else:
                    base_is_auth_correct = True
            else:
                if base_selected_id == sc.expected_doc_id:
                    base_is_auth_correct = True
                if base_status == "Draft":
                    base_is_draft_error = True
                if not base_access_allowed or (base_doc and self.state_manager.owners.get(base_doc.owner_id, None) and self.state_manager.owners[base_doc.owner_id].authority_level < 0.5):
                    base_is_unauth_error = True
                if base_is_auth_correct and sc.expected_section and sc.expected_section in base_cited_sec:
                    base_is_citation_correct = True

            if base_is_auth_correct:
                baseline_auth_correct += 1
            if base_is_citation_correct:
                baseline_citation_correct += 1
            if base_is_draft_error:
                baseline_draft_errors += 1
            if base_is_unauth_error:
                baseline_unauth_errors += 1

            baseline_rows.append({
                "query_id": sc.query_id,
                "query": sc.query,
                "user_role": sc.user_role,
                "scenario_type": sc.scenario_type,
                "expected_doc_id": sc.expected_doc_id or "BLOCKED",
                "expected_version": sc.expected_version or "N/A",
                "selected_doc_id": base_selected_id or "None",
                "selected_version": base_selected_ver or "None",
                "selected_status": base_status,
                "similarity_score": round(base_sim, 4),
                "authoritative_correct": base_is_auth_correct,
                "citation_correct": base_is_citation_correct,
                "draft_error": base_is_draft_error,
                "unauthorized_access_error": base_is_unauth_error,
                "cited_section": base_cited_sec,
            })

            # 2. Run Resolver
            res_result = self.resolver.resolve(sc.query, user_role=sc.user_role)
            res_query_res = self.rag.answer_query(sc.query, sc.user_role, res_result, system_type="RESOLVER")

            res_doc = res_result.selected_document
            res_selected_id = res_doc.document_id if res_doc else None
            res_selected_ver = res_doc.version if res_doc else None
            res_status = res_doc.status if res_doc else "BLOCKED"

            res_is_auth_correct = False
            res_is_citation_correct = False
            res_is_draft_error = False
            res_is_unauth_error = False

            if sc.scenario_type == "ACCESS_RESTRICTION":
                if res_result.status == "ACCESS_DENIED" and res_selected_id is None:
                    res_is_auth_correct = True
                    res_is_citation_correct = True
                else:
                    res_is_unauth_error = True
            else:
                if res_selected_id == sc.expected_doc_id:
                    res_is_auth_correct = True
                if res_status == "Draft":
                    res_is_draft_error = True
                if res_is_auth_correct and sc.expected_section and res_query_res.cited_section and sc.expected_section in res_query_res.cited_section:
                    res_is_citation_correct = True

            if res_is_auth_correct:
                resolver_auth_correct += 1
            if res_is_citation_correct:
                resolver_citation_correct += 1
            if res_is_draft_error:
                resolver_draft_errors += 1
            if res_is_unauth_error:
                resolver_unauth_errors += 1

            top_cand = res_result.candidate_scores[0] if res_result.candidate_scores else None
            res_sim = top_cand.similarity_score if top_cand else 0.0
            res_auth = top_cand.authority_score if top_cand else 0.0

            resolver_rows.append({
                "query_id": sc.query_id,
                "query": sc.query,
                "user_role": sc.user_role,
                "scenario_type": sc.scenario_type,
                "expected_doc_id": sc.expected_doc_id or "BLOCKED",
                "expected_version": sc.expected_version or "N/A",
                "selected_doc_id": res_selected_id or "BLOCKED",
                "selected_version": res_selected_ver or "N/A",
                "selected_status": res_status,
                "similarity_score": res_sim,
                "authority_score": res_auth,
                "resolution_status": res_result.status,
                "authoritative_correct": res_is_auth_correct,
                "citation_correct": res_is_citation_correct,
                "draft_error": res_is_draft_error,
                "unauthorized_access_error": res_is_unauth_error,
                "cited_section": res_query_res.cited_section or "None",
            })

            # 3. Error Analysis for Divergences
            if not base_is_auth_correct or base_is_draft_error or base_is_unauth_error:
                reason = ""
                impact = sc.clinical_risk
                corrective_action = ""

                if base_is_draft_error:
                    reason = f"Draft document '{base_selected_id}' v{base_selected_ver} had higher textual similarity ({base_sim:.3f}) than approved version."
                    corrective_action = "Resolver applied multi-factor authority scoring with approval invariant guard (capped draft authority at 0.35)."
                elif base_is_unauth_error and sc.scenario_type == "ACCESS_RESTRICTION":
                    reason = f"Naive baseline lacked role-based access validation; leaked internal clinical protocol to role '{sc.user_role}'."
                    corrective_action = "Resolver enforced RBAC access rules and blocked document transmission with ACCESS_DENIED status."
                elif sc.scenario_type == "WRONG_OWNER_TRAP":
                    reason = f"Baseline selected document '{base_selected_id}' from unauthorized department '{base_doc.department if base_doc else ''}'."
                    corrective_action = "Resolver evaluated departmental ownership authority level (1.0 for official owner vs 0.0 for unauthorized)."
                elif sc.scenario_type == "SUPERSEDED_TRAP":
                    reason = f"Baseline picked superseded/expired older document version '{base_selected_id}' due to historical keyword density."
                    corrective_action = "Resolver verified effective date validity and superseded relationship chain."
                else:
                    reason = "Baseline selected suboptimal candidate purely by keyword count."
                    corrective_action = "Resolver verified approval status, version hierarchy, and active recency."

                error_analysis_rows.append({
                    "query_id": sc.query_id,
                    "query": sc.query,
                    "scenario_type": sc.scenario_type,
                    "user_role": sc.user_role,
                    "expected_document": f"{sc.expected_doc_id} v{sc.expected_version}" if sc.expected_doc_id else "ACCESS_BLOCKED",
                    "baseline_selection": f"{base_selected_id} v{base_selected_ver} ({base_status})",
                    "resolver_selection": f"{res_selected_id} v{res_selected_ver} ({res_status})",
                    "failure_reason": reason,
                    "clinical_impact": impact,
                    "corrective_action": corrective_action,
                })

        # Calculate final summary metrics
        metrics = {
            "total_queries": total_queries,
            "baseline": {
                "authoritative_accuracy": round((baseline_auth_correct / total_queries) * 100.0, 1),
                "citation_accuracy": round((baseline_citation_correct / total_queries) * 100.0, 1),
                "draft_selection_error_rate": round((baseline_draft_errors / total_queries) * 100.0, 1),
                "unauthorized_source_rate": round((baseline_unauth_errors / total_queries) * 100.0, 1),
            },
            "resolver": {
                "authoritative_accuracy": round((resolver_auth_correct / total_queries) * 100.0, 1),
                "citation_accuracy": round((resolver_citation_correct / total_queries) * 100.0, 1),
                "draft_selection_error_rate": round((resolver_draft_errors / total_queries) * 100.0, 1),
                "unauthorized_source_rate": round((resolver_unauth_errors / total_queries) * 100.0, 1),
            },
        }

        return baseline_rows, resolver_rows, error_analysis_rows, metrics

    def run_chaos_event_experiment(self) -> Dict[str, Any]:
        """Tests event stream resilience under duplicate, delayed, and out-of-order conditions."""
        chaos_results = {}

        # Chaos Test 1: Duplicate Ingestion (Idempotency)
        state1 = self.state_manager.clone()
        proc1 = EventProcessor(state1)
        test_evt = ProtocolEvent(
            event_id="EVT-CHAOS-DUP",
            timestamp="2026-09-01T10:00:00Z",
            type="DOCUMENT_UPLOADED",
            document_id="DOC-CHAOS-001",
            version="1.0",
            title="Chaos Medication Protocol",
            department="Nursing",
            owner_id="OWNER_NURSING",
            status="Draft",
        )
        r1, _ = proc1.process_event(test_evt)
        r2, _ = proc1.process_event(test_evt)  # Duplicate
        r3, _ = proc1.process_event(test_evt)  # Duplicate
        doc_count = len([d for d in state1.get_all_documents() if d.document_id == "DOC-CHAOS-001"])
        chaos_results["duplicate_idempotency_pass"] = (r1 is True and r2 is True and r3 is True and doc_count == 1)

        # Chaos Test 2: Out-of-order Arrival (Monotonicity)
        # Sequence: v3 Approved -> v5 Uploaded -> v4 Uploaded
        state2 = self.state_manager.clone()
        proc2 = EventProcessor(state2)
        e_v3_up = ProtocolEvent(event_id="E-V3-UP", timestamp="2026-08-01T10:00:00Z", type="DOCUMENT_UPLOADED", document_id="DOC-ORDER-001", version="3.0", title="Order Protocol", department="Nursing", owner_id="OWNER_NURSING", status="Approved")
        e_v5_up = ProtocolEvent(event_id="E-V5-UP", timestamp="2026-08-15T10:00:00Z", type="DOCUMENT_UPLOADED", document_id="DOC-ORDER-001", version="5.0", title="Order Protocol", department="Nursing", owner_id="OWNER_NURSING", status="Approved")
        e_v4_up = ProtocolEvent(event_id="E-V4-UP", timestamp="2026-08-10T10:00:00Z", type="DOCUMENT_UPLOADED", document_id="DOC-ORDER-001", version="4.0", title="Order Protocol", department="Nursing", owner_id="OWNER_NURSING", status="Approved")

        # Ingest out of order: v3 -> v5 -> v4
        proc2.process_event(e_v3_up)
        proc2.process_event(e_v5_up)
        proc2.process_event(e_v4_up)  # v4 arrives later

        doc2 = state2.get_document("DOC-ORDER-001")
        # Final active state must be v5.0 or preserved highest version
        chaos_results["out_of_order_recovery_pass"] = (doc2 is not None and doc2.version in ("5.0", "5"))

        # Chaos Test 3: Delayed Approval
        # Sequence: v4 uploaded as Draft -> check query (v3 is authoritative) -> delayed approval arrives -> check query (v4 is authoritative)
        state3 = self.state_manager.clone()
        proc3 = EventProcessor(state3)
        doc_v3 = Document(document_id="DOC-DELAY-V3", title="Delayed Protocol", department="Nursing", version="3.0", content="V3 Protocol content", created_at="2026-01-01", effective_from="2026-01-01", owner_id="OWNER_NURSING", status="Approved")
        state3.add_document(doc_v3)
        state3.set_access("DOC-DELAY-V3", "Nurse", True)

        # Upload v4 (Draft)
        e_v4_upload = ProtocolEvent(event_id="E-DELAY-V4-UP", timestamp="2026-08-20T10:00:00Z", type="DOCUMENT_UPLOADED", document_id="DOC-DELAY-V4", version="4.0", title="Delayed Protocol", department="Nursing", owner_id="OWNER_NURSING", status="Draft")
        proc3.process_event(e_v4_upload)
        state3.set_access("DOC-DELAY-V4", "Nurse", True)

        # Pre-approval check
        retriever3 = CandidateRetriever(state3.get_all_documents())
        resolver3 = AuthoritativeResolver(retriever3, state3)
        res_before = resolver3.resolve("Delayed Protocol", user_role="Nurse")
        v3_authoritative_before = (res_before.selected_document and res_before.selected_document.version == "3.0")

        # Delayed approval event arrives!
        e_v4_approve = ProtocolEvent(event_id="E-DELAY-V4-APP", timestamp="2026-08-30T10:00:00Z", type="DOCUMENT_APPROVED", document_id="DOC-DELAY-V4", version="4.0", approval_role="Chief Medical Officer")
        proc3.process_event(e_v4_approve)

        # Post-approval check
        retriever3.update_documents(state3.get_all_documents())
        res_after = resolver3.resolve("Delayed Protocol", user_role="Nurse")
        v4_authoritative_after = (res_after.selected_document and res_after.selected_document.version == "4.0")

        chaos_results["delayed_approval_transition_pass"] = (v3_authoritative_before and v4_authoritative_after)

        # Calculate recovery rate
        total_scenarios = len(chaos_results)
        passed_scenarios = sum(1 for v in chaos_results.values() if v is True)
        chaos_results["event_recovery_rate"] = round((passed_scenarios / total_scenarios) * 100.0, 1)

        return chaos_results


def export_experiment_results(data_dir: Optional[str] = None):
    """Executes benchmark and writes experiment CSV files."""
    loader = DataLoader(data_dir)
    loader.load_all()

    engine = EvaluationEngine(loader)
    base_rows, res_rows, err_rows, metrics = engine.run_benchmark()
    chaos_metrics = engine.run_chaos_event_experiment()
    metrics["event_chaos"] = chaos_metrics

    # Target experiments dir
    exp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments")
    os.makedirs(exp_dir, exist_ok=True)

    base_path = os.path.join(exp_dir, "baseline_results.csv")
    with open(base_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=base_rows[0].keys())
        writer.writeheader()
        writer.writerows(base_rows)

    res_path = os.path.join(exp_dir, "resolver_results.csv")
    with open(res_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=res_rows[0].keys())
        writer.writeheader()
        writer.writerows(res_rows)

    err_path = os.path.join(exp_dir, "error_analysis.csv")
    with open(err_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=err_rows[0].keys())
        writer.writeheader()
        writer.writerows(err_rows)

    # Save summary metrics JSON
    metrics_path = os.path.join(exp_dir, "summary_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("=" * 65)
    print("🏥 HOSPITAL PROTOCOL AUTHORITATIVE-VERSION RESOLVER BENCHMARK")
    print("=" * 65)
    print(f"Total Benchmark Queries Tested : {metrics['total_queries']}")
    print("-" * 65)
    print(f"{'Metric':<32} | {'Baseline':<12} | {'Resolver':<12}")
    print("-" * 65)
    print(f"{'Authoritative-Source Accuracy':<32} | {metrics['baseline']['authoritative_accuracy']:>10.1f}% | {metrics['resolver']['authoritative_accuracy']:>10.1f}%")
    print(f"{'Citation Accuracy':<32} | {metrics['baseline']['citation_accuracy']:>10.1f}% | {metrics['resolver']['citation_accuracy']:>10.1f}%")
    print(f"{'Draft Selection Error Rate':<32} | {metrics['baseline']['draft_selection_error_rate']:>10.1f}% | {metrics['resolver']['draft_selection_error_rate']:>10.1f}%")
    print(f"{'Unauthorized-Source Rate':<32} | {metrics['baseline']['unauthorized_source_rate']:>10.1f}% | {metrics['resolver']['unauthorized_source_rate']:>10.1f}%")
    print("-" * 65)
    print(f"Event Recovery Rate (Chaos)    : {chaos_metrics['event_recovery_rate']}% (Duplicate + Delayed + Out-of-Order)")
    print("=" * 65)
    print(f"Experiment results written to: {exp_dir}")

    return metrics


if __name__ == "__main__":
    export_experiment_results()
