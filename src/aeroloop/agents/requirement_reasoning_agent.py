from typing import Any, Dict, List
import json
from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.requirement import (
    RequirementReasoningInput, 
    RequirementReasoningResult,
    CandidateRequirement,
    FinalRequirement,
    ResolvedAssumption,
    RequirementConflict,
    RequirementQualityReport
)
from aeroloop.schemas.traceability import TraceLink
from aeroloop.orchestration.vector_store import KnowledgeBase

class RequirementReasoningAgent(BaseAIAgent):
    """
    Merges all candidate requirements, resolves conflicts, and derives the FinalRequirement set (Reasoning).
    It queries the KnowledgeBase for evidence when making assumptions.
    """
    def __init__(self, llm_model=None, **kwargs):
        super().__init__(
            name="Requirement Reasoning Agent",
            description="Merges candidates, resolves conflicts, and produces the FinalRequirement set.",
            **kwargs
        )
        self.llm_model = llm_model
        try:
            self.kb = KnowledgeBase()
        except Exception:
            self.kb = None

    def refine(self, request: RequirementReasoningInput) -> RequirementReasoningResult:
        """
        Merges candidate requirements, detects conflicts, and resolves them.
        """
        if not self.llm_model:
            return self._fail_result(request, "LLM model not provided")

        kb_context = {}
        if self.kb:
            for q in request.unresolved_questions:
                # Retrieve similar past requirements or rules for context
                res = self.kb.search_similar_requirements(q, n_results=2)
                kb_context[q] = res

        prompt = self._build_prompt(request, kb_context)
        
        try:
            response_text = self.llm_model.generate(prompt)
            # Find JSON block
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                response_json = json.loads(response_text[start:end+1])
            else:
                raise ValueError("No JSON object found in response.")

            # Construct final requirements
            final_reqs = []
            for r in response_json.get("final_requirements", []):
                # Ensure missing fields are populated with defaults
                r["requirement_id"] = r.get("requirement_id", "REQ-UNKNOWN")
                r["mission_id"] = request.mission_profile.mission_id if hasattr(request.mission_profile, "mission_id") else "M-UNKNOWN"
                r["priority"] = r.get("priority", "medium")
                r["severity"] = r.get("severity", "medium")
                r["verification_target"] = r.get("verification_target", "aircraft_candidate")
                r["runtime_rule_ready"] = r.get("runtime_rule_ready", False)
                
                # Validation fallback for requirement_type
                if r.get("requirement_type") not in ["hard_constraint", "soft_objective", "report_only", "manual_review"]:
                    r["requirement_type"] = "report_only"
                    
                final_reqs.append(FinalRequirement(**r))
                
            resolved = [ResolvedAssumption(**a) for a in response_json.get("resolved_assumptions", [])]
            conflicts = [RequirementConflict(**c) for c in response_json.get("conflicts_detected", [])]
            rem_q = response_json.get("remaining_unresolved_questions", [])
            from aeroloop.schemas.aircraft import ConceptBaseline
            cb_data = response_json.get("concept_baseline")
            concept_baseline = ConceptBaseline(**cb_data) if cb_data else None

            status = "success"
            if rem_q:
                status = "needs_hitl"
                
            report = RequirementQualityReport(
                total_candidate_requirements=len(request.candidate_requirements),
                total_final_requirements=len(final_reqs),
                hard_constraints=sum(1 for r in final_reqs if r.requirement_type == "hard_constraint"),
                soft_objectives=sum(1 for r in final_reqs if r.requirement_type == "soft_objective"),
                report_only_requirements=sum(1 for r in final_reqs if r.requirement_type == "report_only"),
                measurable_requirements=len(final_reqs),
                non_measurable_requirements=0,
                runtime_rule_ready_count=sum(1 for r in final_reqs if r.runtime_rule_ready),
                unresolved_conflicts=len(conflicts),
                readiness_for_simulation="ready" if not rem_q else "needs_user_clarification",
                summary="Reasoning completed successfully."
            )

            return RequirementReasoningResult(
                run_id=request.run_id,
                status=status,
                concept_baseline=concept_baseline,
                final_requirements=final_reqs,
                resolved_assumptions=resolved,
                remaining_unresolved_questions=rem_q,
                conflicts_detected=conflicts,
                trace_links=[],
                quality_report=report
            )

        except Exception as e:
            return self._fail_result(request, f"Reasoning failed: {str(e)}")

    def _fail_result(self, request: RequirementReasoningInput, error: str) -> RequirementReasoningResult:
        report = RequirementQualityReport(
            total_candidate_requirements=len(request.candidate_requirements),
            total_final_requirements=0, hard_constraints=0, soft_objectives=0, report_only_requirements=0,
            measurable_requirements=0, non_measurable_requirements=0, runtime_rule_ready_count=0, unresolved_conflicts=0,
            readiness_for_simulation="not_ready", summary=error
        )
        return RequirementReasoningResult(
            run_id=request.run_id, status="failed", concept_baseline=None, final_requirements=[],
            resolved_assumptions=[], remaining_unresolved_questions=request.unresolved_questions,
            conflicts_detected=[], trace_links=[], quality_report=report
        )

    def _build_prompt(self, request: RequirementReasoningInput, kb_context: Dict) -> str:
        candidates_str = json.dumps([c.dict() for c in request.candidate_requirements], indent=2, default=str)
        mission_str = request.mission_profile.json()
        unresolved_str = json.dumps(request.unresolved_questions, indent=2)
        kb_str = json.dumps(kb_context, indent=2, default=str)
        
        return f"""
You are the RequirementReasoningAgent for an aerospace design workflow.
Your task is to merge candidate requirements into a cohesive FinalRequirement list, and more importantly, resolve any unresolved_questions using aggressive but plausible baseline assumptions.

Input Mission:
{mission_str}

Candidate Requirements:
{candidates_str}

Unresolved Questions:
{unresolved_str}

Vector DB Context (Use this as evidence if available):
{kb_str}

Instructions:
1. Review the unresolved questions. If a parameter (like payload) is missing, invent a reasonable standard value (e.g. 100kg per passenger).
2. For ANY new requirements you generate, the `requirement_type` MUST be strictly one of: "hard_constraint", "soft_objective", "report_only", or "manual_review". Do NOT use the word "assumption" here.
3. You MUST fully populate ALL OpenVSP architectural parameters in the `concept_baseline` based on mission context. These include: `target_rotor_count`, `max_wingspan_m`, `max_length_m`, `fuselage_width_m_target`, and `fuselage_height_m_target`. If not specified, invent reasonable constraints (e.g., UAM vertiports might dictate max_wingspan_m=15.0).
4. synthesize the `final_requirements` into a high-level `concept_baseline` which acts as the SizingDraft for the SizingAgent. Physics-derived fields like mtow_kg and wing_area_m2 should be left blank as they will be calculated downstream.

Format your response STRICTLY as a JSON object matching this structure:
{{
  "concept_baseline": {{
    "concept_id": "CONCEPT-001",
    "aircraft_type": "lift_cruise_vtol",
    "target_range_km": 100.0,
    "target_cruise_speed_mps": 30.0,
    "target_payload_kg": 400.0,
    "battery_reserve_percent_target": 20.0,
    "noise_level_target_db": 65.0,
    "target_rotor_count": 8,
    "max_wingspan_m": 15.0,
    "max_length_m": 15.0,
    "fuselage_width_m_target": 1.5,
    "fuselage_height_m_target": 1.5,
    "assumptions": ["Standard 100kg per passenger payload"]
  }},
  "final_requirements": [
    {{
      "requirement_id": "REQ-001",
      "title": "...",
      "description": "...",
      "category": "performance",
      "requirement_type": "hard_constraint",
      "variable_name": "payload_kg",
      "operator": ">=",
      "threshold": 400,
      "source_candidate_ids": [],
      "rationale": "..."
    }}
  ],
  "resolved_assumptions": [
    {{
      "question": "What is payload?",
      "assumed_value": "400 kg",
      "rationale": "Standard assumption",
      "confidence": 0.8
    }}
  ],
  "remaining_unresolved_questions": [],
  "conflicts_detected": []
}}
"""

    def export_markdown_report(self, request: RequirementReasoningInput, result: RequirementReasoningResult) -> str:
        """
        Generates a human-readable markdown report summarizing the final requirements and baseline assumptions.
        This serves as the 'blueprint' before handing off to the SizingAgent.
        """
        md = []
        md.append(f"# System Requirements Report")
        md.append(f"**Run ID:** {result.run_id}")
        md.append(f"**Status:** {result.status}\\n")
        
        md.append("## 1. Mission Profile Summary")
        m = request.mission_profile
        md.append(f"- **Mission Type:** {m.mission_type}")
        md.append(f"- **Operation Area:** {m.operation_area}")
        md.append(f"- **Origin -> Destination:** {m.origin} -> {m.destination}")
        md.append(f"- **Passenger Count:** {m.passenger_count}\\n")

        md.append("## 2. Concept Baseline (Sizing Draft)")
        if result.concept_baseline:
            cb = result.concept_baseline
            md.append(f"- **Aircraft Type:** {cb.aircraft_type}")
            md.append(f"- **Target Range (km):** {cb.target_range_km}")
            md.append(f"- **Target Cruise Speed (m/s):** {cb.target_cruise_speed_mps}")
            md.append(f"- **Target Payload (kg):** {cb.target_payload_kg}")
            md.append(f"- **Battery Reserve Target (%):** {cb.battery_reserve_percent_target}\\n")
        else:
            md.append("*No concept baseline generated.*\\n")

        md.append("## 3. Resolved Assumptions (Baseline)")
        if not result.resolved_assumptions:
            md.append("*No assumptions needed or resolved.*\\n")
        else:
            for a in result.resolved_assumptions:
                md.append(f"### Q: {a.question}")
                md.append(f"- **Assumed Value:** `{a.assumed_value}`")
                md.append(f"- **Rationale:** {a.rationale}")
                md.append(f"- **Confidence:** {a.confidence}\\n")

        md.append("## 3. Final Engineering Requirements")
        if not result.final_requirements:
            md.append("*No final requirements generated.*\\n")
        else:
            md.append("| ID | Variable | Operator | Threshold | Type |")
            md.append("|---|---|---|---|---|")
            for req in result.final_requirements:
                var_name = req.variable_name or "N/A"
                op = req.operator or ""
                thresh = str(req.threshold) if req.threshold is not None else ""
                md.append(f"| {req.requirement_id} | `{var_name}` | {op} | {thresh} {req.unit or ''} | {req.requirement_type} |")
            md.append("\\n")

        md.append("## 4. Remaining Unresolved Questions (HITL Required)")
        if not result.remaining_unresolved_questions:
            md.append("*All clear. Ready for Sizing.*\\n")
        else:
            for q in result.remaining_unresolved_questions:
                md.append(f"- ⚠️ {q}")
            md.append("\\n")
            
        return "\\n".join(md)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        req_dict = state.get("requirement_reasoning_input")
        if not req_dict:
            return state
            
        if isinstance(req_dict, dict):
            req = RequirementReasoningInput(**req_dict)
        else:
            req = req_dict
            
        result = self.refine(req)
        state["requirement_reasoning_result"] = result
        return state
