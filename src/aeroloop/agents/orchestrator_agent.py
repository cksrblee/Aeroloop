from typing import Any, Dict
from aeroloop.orchestration.state import WorkflowState

class OrchestratorAgent:
    """
    Central router for the AeroLoop bidirectional workflow.
    Evaluates the global WorkflowState and determines the next node to execute.
    """
    def __init__(self):
        pass

    def __call__(self, state: WorkflowState) -> dict:
        """
        LangGraph node function. Evaluates state and sets next_node.
        """
        status = state.get("status", "running")
        feedback_history = state.get("feedback_history", [])
        
        # 1. Handle Errors / Feedback (Bidirectional Routing)
        if status == "error" and feedback_history:
            last_feedback = feedback_history[-1].lower()
            
            # Prevent infinite loops (simple heuristic)
            if len(feedback_history) > 3:
                return {"next_node": "END", "status": "failed", "errors": [{"error": "Infinite loop detected in workflow."}]}
                
            # Route back to mission parsing if missing info or mission related conflict
            if "missing" in last_feedback or "mission" in last_feedback:
                return {"next_node": "mission_parsing", "status": "running"}
            
            # Default error handling
            return {"next_node": "END", "status": "failed"}

        # 2. Linear Progression if no errors
        mission_profile = state.get("mission_profile")
        candidate_reqs = state.get("candidate_requirements", [])
        cert_result = state.get("certification_compliance_result")
        
        if not mission_profile:
            return {"next_node": "mission_parsing", "status": "running"}
            
        if not candidate_reqs:
            return {"next_node": "customer_requirement", "status": "running"}
            
        unresolved_questions = state.get("unresolved_questions", [])
        if unresolved_questions:
            return {"next_node": "config_design", "status": "running", "feedback_history": ["Unresolved questions detected. Routing to Config Design / HITL agent."]}
            
        if not cert_result:
            return {"next_node": "certification_compliance", "status": "running"}
            
        # 3. Certification Quality Report Routing
        quality_report = cert_result.quality_report
        
        if quality_report.readiness_level == "needs_configuration_detail":
            return {"next_node": "config_design", "status": "running", "feedback_history": ["Please provide detailed AircraftConcept for further certification mapping."]}
            
        if quality_report.readiness_level == "needs_human_certification_review":
            return {"next_node": "END", "status": "paused_for_review", "feedback_history": ["Human certification expert review required."]}
            
        # preliminary or ready_for_concept_review means success for this phase.
        return {"next_node": "END", "status": "completed"}

    def route_edge(self, state: WorkflowState) -> str:
        """
        Conditional edge function for LangGraph.
        Returns the literal string name of the next node.
        """
        next_node = state.get("next_node", "END")
        return next_node
