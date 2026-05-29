from langgraph.graph import StateGraph, END, START
from aeroloop.orchestration.state import WorkflowState
from aeroloop.agents.orchestrator_agent import OrchestratorAgent
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent
from aeroloop.llm.adapters import OpenAIAdapter
from aeroloop.schemas.mission import MissionParsingInput
from datetime import datetime

# Initialize singletons / agents
# We can inject these later, but for simplicity we instantiate them here.
llm_adapter = OpenAIAdapter(model_name="gpt-4o-mini", temperature=0.0)
mission_agent = MissionParsingAgent(llm_model=llm_adapter)
customer_agent = CustomerRequirementAgent()
cert_agent = CertificationComplianceAgent()
orchestrator_agent = OrchestratorAgent()

def mission_parsing_node(state: WorkflowState):
    raw_input = state.get("raw_input")
    if not raw_input:
        return {"status": "error", "feedback_history": ["Missing raw_input for mission_parsing_node"]}
    
    try:
        result = mission_agent.parse(raw_input)
        if result.missing_fields:
            # If there are missing fields, it routes back with an error
            return {
                "mission_profile": result.mission_profile,
                "status": "error",
                "feedback_history": [f"Missing mission fields: {[mf.field_name for mf in result.missing_fields]}"]
            }
        
        return {
            "mission_profile": result.mission_profile,
            "status": "running"
        }
    except Exception as e:
        return {"status": "error", "feedback_history": [f"Mission parsing failed: {str(e)}"]}

def customer_requirement_node(state: WorkflowState):
    mission_profile = state.get("mission_profile")
    if not mission_profile:
        return {"status": "error", "feedback_history": ["Missing mission_profile for customer_requirement_node"]}
        
    try:
        result = customer_agent.analyze(mission_profile)
        
        # Determine if we should report errors back to the orchestrator
        if result.quality_flags and "validation_errors_present" in result.quality_flags:
             return {
                "candidate_requirements": result.candidate_requirements,
                "status": "error",
                "feedback_history": ["Customer requirement validation failed."]
             }
             
        return {
            "candidate_requirements": result.candidate_requirements,
            "assumptions": result.assumptions,
            "status": "running"
        }
    except Exception as e:
        return {"status": "error", "feedback_history": [f"Customer requirement failed: {str(e)}"]}

def certification_compliance_node(state: WorkflowState):
    mission_profile = state.get("mission_profile")
    customer_reqs = state.get("candidate_requirements", [])
    aircraft_concept = state.get("aircraft_concept")
    
    if not mission_profile or not customer_reqs:
        return {"status": "error", "feedback_history": ["Missing mission_profile or customer_reqs for certification_compliance"]}
        
    try:
        from aeroloop.schemas.compliance import CertificationComplianceInput
        from aeroloop.schemas.certification import CertificationSourcePolicy
        
        comp_input = CertificationComplianceInput(
            run_id=state.get("run_id", "unknown_run"),
            mission_profile=mission_profile,
            customer_requirements=customer_reqs,
            aircraft_concept=aircraft_concept,
            certification_source_policy=CertificationSourcePolicy(
                allowed_source_families=["SC_VTOL_SMALL", "SMALL_ROTORCRAFT", "SMALL_AIRCRAFT"],
                allowed_authorities=["EASA", "FAA", "KAS"]
            )
        )
        
        result = cert_agent.analyze(comp_input)
        
        return {
            "certification_compliance_result": result,
            "status": "running"
        }
    except Exception as e:
        return {"status": "error", "feedback_history": [f"Certification compliance failed: {str(e)}"]}

def orchestrator_node(state: WorkflowState):
    return orchestrator_agent(state)

def route_from_orchestrator(state: WorkflowState):
    return orchestrator_agent.route_edge(state)

def create_workflow():
    """
    Creates and compiles the bidirectional LangGraph workflow.
    """
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("mission_parsing", mission_parsing_node)
    workflow.add_node("customer_requirement", customer_requirement_node)
    workflow.add_node("certification_compliance", certification_compliance_node)
    workflow.add_node("orchestrator", orchestrator_node)
    
    # All agent nodes route back to the orchestrator to decide the next step
    workflow.add_edge("mission_parsing", "orchestrator")
    workflow.add_edge("customer_requirement", "orchestrator")
    workflow.add_edge("certification_compliance", "orchestrator")
    
    # Initial edge routes to orchestrator which will decide what to do
    workflow.add_edge(START, "orchestrator")
    
    # Conditional edges from orchestrator
    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "mission_parsing": "mission_parsing",
            "customer_requirement": "customer_requirement",
            "certification_compliance": "certification_compliance",
            "END": END
        }
    )
    
    return workflow.compile()
