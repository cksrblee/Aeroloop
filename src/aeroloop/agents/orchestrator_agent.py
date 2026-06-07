from typing import Any, Dict
from aeroloop.orchestration.state import WorkflowState

class OrchestratorAgent:
    """
    Central router for the AeroLoop cyclic workflow.
    Evaluates the global WorkflowState and determines the next node to execute.
    Supports iterative cycles between Sizing <-> Geometry <-> Simulation,
    and falls back to Mission Parsing if local constraints are unresolvable.
    """
    def __init__(self, max_sizing_iters=3, max_global_iters=3):
        self.max_sizing_iters = max_sizing_iters
        self.max_global_iters = max_global_iters

    def __call__(self, state: WorkflowState) -> dict:
        """
        LangGraph node function. Evaluates state and sets next_node.
        """
        status = state.get("status", "running")
        feedback_history = state.get("feedback_history", [])
        
        sizing_iters = state.get("sizing_iteration_count") or 0
        global_iters = state.get("global_iteration_count") or 0
        
        # 1. Handle Global Loop Constraints
        if global_iters >= self.max_global_iters:
            return {
                "next_node": "END", 
                "status": "failed", 
                "errors": [{"error": "Max global iterations reached. Mission parameters are unfeasible."}]
            }

        # 2. Handle Errors / Bidirectional Escapes
        if status == "error" and feedback_history:
            last_feedback = feedback_history[-1].lower()
            
            # Mission critical errors -> back to mission parsing
            if "missing" in last_feedback or "mission" in last_feedback:
                return {
                    "next_node": "mission_parsing", 
                    "status": "running",
                    "global_iteration_count": global_iters + 1,
                    "sizing_iteration_count": 0 # Reset local count
                }
            
            # Validation failures -> back to requirement reasoning
            if "validation" in last_feedback and "certification" in last_feedback:
                return {
                    "next_node": "requirement_reasoning",
                    "status": "running",
                    "feedback_history": [f"Validation failed. Routing back to RRA to fix baseline."]
                }
            
            # Sizing failures or Simulation failures
            if "sizing" in last_feedback or "geometry" in last_feedback or "simulation" in last_feedback or "aerodynamics" in last_feedback:
                if sizing_iters < self.max_sizing_iters:
                    return {
                        "next_node": "sizing",
                        "status": "running",
                        "sizing_iteration_count": sizing_iters + 1
                    }
                else:
                    # Sizing maxed out, escalate to global loop
                    return {
                        "next_node": "mission_parsing",
                        "status": "running",
                        "global_iteration_count": global_iters + 1,
                        "sizing_iteration_count": 0,
                        "feedback_history": ["Sizing iteration limits reached. Relaxing mission constraints."]
                    }
            
            # Default error handling
            return {"next_node": "END", "status": "failed"}

        # 3. Linear Progression Check
        mission_profile = state.get("mission_profile")
        candidate_reqs = state.get("candidate_requirements", [])
        cert_result = state.get("certification_compliance_result")
        
        if not mission_profile:
            return {"next_node": "mission_parsing", "status": "running"}
            
        if not candidate_reqs:
            return {"next_node": "customer_requirement", "status": "running"}
            
        # Extraction: Retrieve applicable regulations
        if not cert_result:
            return {"next_node": "certification_compliance", "status": "running"}
            
        requirement_reasoning_result = state.get("requirement_reasoning_result")
        unresolved_questions = state.get("unresolved_questions", [])
        
        if not requirement_reasoning_result or unresolved_questions:
            return {"next_node": "requirement_reasoning", "status": "running", "feedback_history": ["Routing to Reasoning agent to merge requirements and make assumptions."]}
            
        # Validation: Verify ConceptBaseline against regulations
        validation_result = state.get("certification_validation_result")
        # If there's no validation result OR if the last validation failed, we need to run it (or we ran it and failed, but wait, if it failed it would be caught by the error handler above and routed to RRA. When RRA finishes, status is 'running'. But validation_result is still in state and is_valid is False!)
        # So we should check if validation_result is valid. If not, route to CVA to check the NEW baseline.
        if not validation_result or not validation_result.is_valid:
            return {"next_node": "certification_validator", "status": "running", "feedback_history": ["Validating the reasoned Concept Baseline against the rules."]}
            
        # 4. Certification Quality Routing (Post-Reasoning)
        quality_report = cert_result.quality_report
        if quality_report.readiness_level == "needs_human_certification_review":
            return {"next_node": "END", "status": "paused_for_review", "feedback_history": ["Human certification expert review required."]}
        
        # Note: If quality_report.readiness_level == "needs_configuration_detail", 
        # it is expected. We proceed to Sizing to generate the configuration detail.
            
        # 5. Cyclic Engineering Flow: Sizing -> Geometry -> Simulation
        sizing_result = state.get("sizing_result")
        if not sizing_result or sizing_result.status == "failed":
            if sizing_result and sizing_result.status == "failed" and sizing_iters >= self.max_sizing_iters:
                return {
                    "next_node": "mission_parsing",
                    "status": "running",
                    "global_iteration_count": global_iters + 1,
                    "sizing_iteration_count": 0,
                    "feedback_history": ["Sizing intrinsically failed. Relaxing constraints."]
                }
            return {
                "next_node": "sizing", 
                "status": "running",
                "sizing_iteration_count": sizing_iters + 1 if sizing_result else sizing_iters
            }
            
        geo_result = state.get("geometry_design_result")
        if not geo_result or geo_result.status == "failed":
            return {"next_node": "geometry_design", "status": "running"}
            
        analysis_result = state.get("analysis_result")
        if not analysis_result:
            return {"next_node": "aerodynamics_analysis", "status": "running"}
            
        # 6. Evaluate Simulation Result
        if analysis_result.status == "failed":
            if sizing_iters < self.max_sizing_iters:
                return {
                    "next_node": "sizing",
                    "status": "running",
                    "sizing_iteration_count": sizing_iters + 1,
                    "feedback_history": [f"Simulation failed: {analysis_result.error}. Routing back to sizing."]
                }
            else:
                return {
                    "next_node": "mission_parsing",
                    "status": "running",
                    "global_iteration_count": global_iters + 1,
                    "sizing_iteration_count": 0,
                    "feedback_history": ["Simulation failed continuously. Sizing iteration limits reached. Relaxing constraints."]
                }
                
        # If we reached here, simulation passed, and we are ready for concept review
        return {"next_node": "END", "status": "completed"}

    def route_edge(self, state: WorkflowState) -> str:
        """
        Conditional edge function for LangGraph.
        Returns the literal string name of the next node.
        """
        next_node = state.get("next_node", "END")
        return next_node
