from langgraph.graph import StateGraph, END, START
from aeroloop.orchestration.state import WorkflowState
from aeroloop.agents.orchestrator_agent import OrchestratorAgent
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent
from aeroloop.agents.certification_validator_agent import CertificationValidatorAgent
from aeroloop.agents.sizing_agent import SizingAgent
from aeroloop.agents.geometry_design_agent import GeometryDesignAgent
from aeroloop.agents.aerodynamics_analysis_agent import AerodynamicsAnalysisAgent
from aeroloop.agents.requirement_reasoning_agent import RequirementReasoningAgent
from aeroloop.llm.adapters import OpenAIAdapter
from aeroloop.schemas.mission import MissionParsingInput
from aeroloop.schemas.traceability import TraceabilityRegistry
from aeroloop.config import config
from datetime import datetime
import hashlib

# Initialize singletons / agents
# We can inject these later, but for simplicity we instantiate them here.
llm_adapter = OpenAIAdapter(model_name="gpt-5.4-mini", temperature=0.0)
mission_agent = MissionParsingAgent(llm_model=llm_adapter)
customer_agent = CustomerRequirementAgent()
cert_agent = CertificationComplianceAgent()
validator_agent = CertificationValidatorAgent()
orchestrator_agent = OrchestratorAgent()
sizing_agent = SizingAgent()
geometry_agent = GeometryDesignAgent()
analysis_agent = AerodynamicsAnalysisAgent()
reasoning_agent = RequirementReasoningAgent(llm_model=llm_adapter)

def mission_parsing_node(state: WorkflowState):
    raw_input = state.get("raw_input")
    if not raw_input:
        return {"status": "error", "feedback_history": ["Missing raw_input for mission_parsing_node"]}
        
    # Initialize run_id and traceability_registry if not present
    run_id = state.get("run_id")
    if not run_id:
        if isinstance(raw_input, MissionParsingInput):
            run_id = f"RUN-{hashlib.md5(raw_input.raw_text.encode()).hexdigest()[:8]}"
        else:
            run_id = f"RUN-{hashlib.md5(str(raw_input).encode()).hexdigest()[:8]}"
            
    registry = state.get("traceability_registry")
    if not registry:
        registry = TraceabilityRegistry()
    
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
            "run_id": run_id,
            "traceability_registry": registry,
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
            "unresolved_questions": result.unresolved_questions,
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

def requirement_reasoning_node(state: WorkflowState):
    from aeroloop.schemas.requirement import RequirementReasoningInput
    
    mission_profile = state.get("mission_profile")
    candidate_reqs = state.get("candidate_requirements", [])
    unresolved_questions = state.get("unresolved_questions", [])
    run_id = state.get("run_id", "unknown_run")
    
    if not mission_profile:
        return {"status": "error", "feedback_history": ["Missing mission_profile for reasoning"]}
        
    req = RequirementReasoningInput(
        run_id=run_id,
        mission_profile=mission_profile,
        candidate_requirements=candidate_reqs,
        unresolved_questions=unresolved_questions
    )
    
    result = reasoning_agent.refine(req)
    
    # Store TraceLinks to Registry
    registry = state.get("traceability_registry")
    if registry and result.trace_links:
        for link in result.trace_links:
            registry.add_link(link)
            
    # Clear unresolved questions from the main state if resolved, and append any remaining
    new_unresolved = result.remaining_unresolved_questions
    
    return {
        "requirement_reasoning_result": result,
        "aircraft_concept": result.concept_baseline,
        "candidate_requirements": result.final_requirements, # Feed final back into state for Sizing
        "unresolved_questions": new_unresolved,
        "traceability_registry": registry,
        "status": "running" if not new_unresolved else "paused_for_hitl"
    }

def certification_validator_node(state: WorkflowState):
    from aeroloop.schemas.compliance import CertificationValidationInput
    
    concept_baseline = state.get("aircraft_concept")
    comp_result = state.get("certification_compliance_result")
    
    if not concept_baseline or not comp_result:
        return {"status": "error", "feedback_history": ["Missing concept_baseline or compliance_result for validation"]}
        
    req = CertificationValidationInput(
        run_id=state.get("run_id", "unknown_run"),
        concept_baseline=concept_baseline,
        compliance_result=comp_result
    )
    
    result = validator_agent.validate(req)
    
    if not result.is_valid:
        # Feed the violations back as unresolved questions so RRA can fix them!
        current_unresolved = state.get("unresolved_questions", [])
        for v in result.violations:
            q = f"Certification Validation Failed: {v}. Please adjust the ConceptBaseline to satisfy this."
            if q not in current_unresolved:
                current_unresolved.append(q)
                
        return {
            "certification_validation_result": result,
            "unresolved_questions": current_unresolved,
            "status": "error",
            "feedback_history": [f"Certification Validation Failed: {result.violations}"]
        }
        
    return {
        "certification_validation_result": result,
        "status": "running"
    }

def sizing_node(state: WorkflowState):
    from aeroloop.schemas.engineering import SizingConfig, SizingRequest
    
    mission_profile = state.get("mission_profile")
    candidate_reqs = state.get("candidate_requirements", [])
    
    if not mission_profile:
        return {"status": "error", "feedback_history": ["Missing mission_profile for sizing"]}
        
    run_id = state.get("run_id", "run-001")
    candidate_id = f"AC-{hashlib.md5((run_id + 'AC').encode()).hexdigest()[:8]}"
    mission_id = mission_profile.mission_id if hasattr(mission_profile, 'mission_id') else f"M-{hashlib.md5(run_id.encode()).hexdigest()[:8]}"
    
    concept_baseline = state.get("aircraft_concept")
    if not concept_baseline:
        return {"status": "error", "feedback_history": ["Missing aircraft_concept (ConceptBaseline) for sizing"]}

    req = SizingRequest(
        sizing_request_id=f"REQ-{hashlib.md5((run_id + candidate_id).encode()).hexdigest()[:8]}",
        run_id=run_id,
        mission_id=mission_id,
        candidate_id=candidate_id,
        mission_profile=mission_profile,
        concept_baseline=concept_baseline,
        sizing_config=SizingConfig(),
        final_requirements=candidate_reqs
    )
    
    result = sizing_agent.size(req)
    
    # Dump result to JSON for user visibility
    import json
    run_dir = config.get_run_dir(run_id)
    output_path = run_dir / f"sizing_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
    
    # Store TraceLinks to Registry
    registry = state.get("traceability_registry")
    if registry and result.trace_links:
        for link in result.trace_links:
            registry.add_link(link)
    
    # Handle mission revision request (HITL)
    if result.status == "mission_revision_required":
        current_unresolved = state.get("unresolved_questions", [])
        hitl_prompt = f"Engineering Sizing Failed: {result.conflict_report}. Please provide a revised mission parameter (e.g., lower range or payload) to resolve this physical contradiction."
        if hitl_prompt not in current_unresolved:
            current_unresolved.append(hitl_prompt)
            
        return {
            "sizing_result": result,
            "status": "paused_for_hitl",
            "unresolved_questions": current_unresolved,
            "feedback_history": [f"Sizing Failed, HITL required: {result.conflict_report}"]
        }
        
    return {
        "sizing_result": result,
        "status": "running" if result.status in ["success", "success_with_warnings"] else "error",
        "feedback_history": [f"Sizing Failed: {', '.join(result.warnings)}"] if result.status == "failed" else [],
        "traceability_registry": registry
    }

def geometry_design_node(state: WorkflowState):
    from aeroloop.schemas.geometry import GeometryDesignRequest, ValidationOptions
    
    sizing_result = state.get("sizing_result")
    if not sizing_result or not sizing_result.geometry_parameter_set:
        return {"status": "error", "feedback_history": ["Missing sizing_result for geometry design"]}
        
    run_id = state.get("run_id", "run-001")
    config_id = f"CFG-{hashlib.md5((run_id + sizing_result.candidate_id).encode()).hexdigest()[:8]}"
    
    run_dir = config.get_run_dir(run_id)
    geo_out_dir = run_dir / "geometry_output"
    geo_out_dir.mkdir(parents=True, exist_ok=True)
    
    req = GeometryDesignRequest(
        geometry_request_id=f"GEO-REQ-{hashlib.md5(config_id.encode()).hexdigest()[:8]}",
        run_id=run_id,
        candidate_id=sizing_result.candidate_id,
        configuration_id=config_id,
        vehicle_type=sizing_result.geometry_parameter_set.aircraft_type,
        design_parameters=sizing_result.geometry_parameter_set.dict(exclude_none=True),
        output_directory=str(geo_out_dir),
        validation_options=ValidationOptions(validate_mesh=False)
    )
    
    result = geometry_agent.process_request(req)
    
    # Store TraceLinks to Registry
    registry = state.get("traceability_registry")
    if registry and result.trace_links:
        for link in result.trace_links:
            registry.add_link(link)
    
    return {
        "geometry_design_result": result,
        "status": "running",
        "traceability_registry": registry
    }

def aerodynamics_analysis_node(state: WorkflowState):
    from aeroloop.schemas.aerodynamics import AerodynamicsAnalysisRequest
    
    geo_result = state.get("geometry_design_result")
    if not geo_result or not geo_result.geometry_vsp3_path:
        return {"status": "error", "feedback_history": ["Missing geometry_design_result for simulation"]}
        
    from aeroloop.schemas.aerodynamics import AeroAnalysisConfig, AircraftCandidate, GeometryArtifacts
    import hashlib

    run_id = state.get("run_id", "run-001")
    candidate_id = geo_result.candidate_id if hasattr(geo_result, "candidate_id") else "AC-001"
    mission_id = f"M-{hashlib.md5(run_id.encode()).hexdigest()[:8]}"

    req = AerodynamicsAnalysisRequest(
        aero_analysis_request_id=f"AERO-REQ-{hashlib.md5((run_id + candidate_id).encode()).hexdigest()[:8]}",
        run_id=run_id,
        mission_id=mission_id,
        candidate_id=candidate_id,
        geometry_result_id=geo_result.geometry_result_id if hasattr(geo_result, "geometry_result_id") else "GEO-RES-001",
        aircraft_candidate=AircraftCandidate(
            candidate_id=candidate_id,
            aircraft_type="unknown",
            template_id="TPL-001"
        ),
        geometry_artifacts=GeometryArtifacts(
            vsp3_file_path=geo_result.geometry_vsp3_path
        ),
        analysis_config=AeroAnalysisConfig(
            analysis_backend="openvsp_vspaero",
            analysis_fidelity="low",
            run_mass_properties=True,
            run_vspaero=False # Simplified to mass props by default for this workflow node unless specified
        ),
        output_directory="/tmp"
    )
    
    # We pass the request directly via dict to run() matching BaseAIAgent expectations
    res = analysis_agent.run({"analysis_request": req})
    
    # Extract the result and return state updates
    analysis_result = res.get("analysis_result")
    if not analysis_result:
        return {"status": "error", "feedback_history": ["Analysis failed to return a result."]}
        
    # We can pass success back or error back. The orchestrator agent handles cyclic routing.
    return {
        "analysis_result": analysis_result,
        "status": "error" if analysis_result.status == "failed" else "running",
        "feedback_history": [f"Simulation failed: {analysis_result.error}"] if analysis_result.status == "failed" else []
    }

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
    workflow.add_node("requirement_reasoning", requirement_reasoning_node)
    workflow.add_node("certification_validator", certification_validator_node)
    workflow.add_node("sizing", sizing_node)
    workflow.add_node("geometry_design", geometry_design_node)
    workflow.add_node("aerodynamics_analysis", aerodynamics_analysis_node)
    workflow.add_node("orchestrator", orchestrator_node)
    
    # All agent nodes route back to the orchestrator to decide the next step
    workflow.add_edge("mission_parsing", "orchestrator")
    workflow.add_edge("customer_requirement", "orchestrator")
    workflow.add_edge("certification_compliance", "orchestrator")
    workflow.add_edge("requirement_reasoning", "orchestrator")
    workflow.add_edge("certification_validator", "orchestrator")
    workflow.add_edge("sizing", "orchestrator")
    workflow.add_edge("geometry_design", "orchestrator")
    workflow.add_edge("aerodynamics_analysis", "orchestrator")
    
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
            "requirement_reasoning": "requirement_reasoning",
            "certification_validator": "certification_validator",
            "sizing": "sizing",
            "geometry_design": "geometry_design",
            "aerodynamics_analysis": "aerodynamics_analysis",
            "END": END
        }
    )
    
    return workflow.compile()
