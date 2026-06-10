from typing import Any
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
llm_adapter = OpenAIAdapter(model_name=config.llm_model_name, temperature=config.llm_temperature)
mission_agent = MissionParsingAgent(llm_model=llm_adapter)
customer_agent = CustomerRequirementAgent()
cert_agent = CertificationComplianceAgent()
validator_agent = CertificationValidatorAgent()
orchestrator_agent = OrchestratorAgent()
sizing_agent = SizingAgent()
geometry_agent = GeometryDesignAgent()
analysis_agent = AerodynamicsAnalysisAgent()
reasoning_agent = RequirementReasoningAgent(llm_model=llm_adapter)

def dump_intermediate_result(run_id: str, filename: str, result_obj: Any):
    from typing import Any
    try:
        run_dir = config.get_run_dir(run_id)
        out_path = run_dir / filename
        if hasattr(result_obj, "model_dump_json"):
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result_obj.model_dump_json(indent=2))
        else:
            import json
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result_obj, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Failed to dump {filename}: {e}")

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
        previous_result = state.get("mission_parsing_result")
        human_input = state.get("human_input")
        print(f"\n[MissionParsingAgent] Extracting mission profile and constraints (Run ID: {run_id})...")
        result = mission_agent.parse(raw_input, previous_result=previous_result, human_input=human_input)
        if result.missing_fields:
            # If there are missing fields, pause for HITL
            return {
                "mission_profile": result.mission_profile,
                "mission_parsing_result": result,
                "status": "paused_for_hitl",
                "awaiting_input_from": "mission_parsing"
            }
        
        dump_intermediate_result(run_id, "mission_parsing_result.json", result)
        return {
            "mission_profile": result.mission_profile,
            "mission_parsing_result": result,
            "human_input": None, # Clear it out
            "awaiting_input_from": None,
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
        run_id = state.get("run_id", "unknown_run")
        print(f"\n[CustomerRequirementAgent] Generating candidate customer and operational requirements (Run ID: {run_id})...")
        result = customer_agent.analyze(mission_profile)
        
        # Determine if we should report errors back to the orchestrator
        if result.quality_flags and "validation_errors_present" in result.quality_flags:
             return {
                "candidate_requirements": result.candidate_requirements,
                "status": "error",
                "feedback_history": ["Customer requirement validation failed."]
             }
             
        run_id = state.get("run_id", "unknown_run")
        dump_intermediate_result(run_id, "customer_requirements_result.json", result)
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
        
        print(f"\n[CertificationComplianceAgent] Identifying applicable certification regulations (Run ID: {comp_input.run_id})...")
        result = cert_agent.analyze(comp_input)
        
        dump_intermediate_result(state.get("run_id", "unknown_run"), "certification_compliance_result.json", result)
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
    
    previous_result = state.get("requirement_reasoning_result")
    human_input = state.get("human_input")
    print(f"\n[RequirementReasoningAgent] Resolving conflicts and synthesizing final requirements (Run ID: {run_id})...")
    result = reasoning_agent.refine(req, previous_result=previous_result, human_input=human_input)
    
    # Store TraceLinks to Registry
    registry = state.get("traceability_registry")
    if registry and result.trace_links:
        for link in result.trace_links:
            registry.add_link(link)
            
    # Clear unresolved questions from the main state if resolved, and append any remaining
    new_unresolved = result.remaining_unresolved_questions
    
    dump_intermediate_result(run_id, "requirement_reasoning_result.json", result)
    
    status = "paused_for_hitl" if new_unresolved else "running"
    
    return {
        "requirement_reasoning_result": result,
        "aircraft_concept": result.concept_baseline,
        "final_requirements": result.final_requirements, # Feed final back into state for Sizing
        "unresolved_questions": new_unresolved,
        "traceability_registry": registry,
        "status": status,
        "awaiting_input_from": "requirement_reasoning" if new_unresolved else None,
        "human_input": None if not new_unresolved else human_input # clear when done
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
    
    print(f"\n[CertificationValidatorAgent] Validating aircraft concept baseline against certification rules (Run ID: {req.run_id})...")
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
        
    dump_intermediate_result(state.get("run_id", "unknown_run"), "certification_validation_result.json", result)
    return {
        "certification_validation_result": result,
        "status": "running"
    }

def sizing_node(state: WorkflowState):
    from aeroloop.schemas.engineering import SizingConfig, SizingRequest
    
    mission_profile = state.get("mission_profile")
    final_reqs = state.get("final_requirements", [])
    
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
        final_requirements=final_reqs
    )
    
    sizing_iters = state.get("sizing_iteration_count", 0) + 1
    print(f"\n[SizingAgent] Running iterative sizing calculations (Candidate: {candidate_id}, Iteration: {sizing_iters})...")
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
    from aeroloop.schemas.geometry import GeometryDesignRequest, GeometryValidationOptions
    
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
        mission_id=sizing_result.mission_id if hasattr(sizing_result, 'mission_id') else "unknown_mission",
        candidate_id=sizing_result.candidate_id,
        configuration_id=config_id,
        vehicle_type=sizing_result.geometry_parameter_set.aircraft_type,
        geometry_template="maximal",
        design_parameters=sizing_result.geometry_parameter_set.dict(exclude_none=True),
        output_directory=str(geo_out_dir),
        validation_options=GeometryValidationOptions(validate_mesh=False)
    )
    
    print(f"\n[GeometryDesignAgent] Generating 3D parametric geometry models (Candidate: {sizing_result.candidate_id}, Vehicle Type: {req.vehicle_type})...")
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
    if not geo_result or not geo_result.geometry_artifacts or not geo_result.geometry_artifacts.vsp3_file_path:
        return {"status": "error", "feedback_history": ["Missing geometry_design_result for simulation"]}
        
    from aeroloop.schemas.aerodynamics import AeroAnalysisConfig, AircraftCandidate, GeometryArtifacts
    import hashlib

    run_id = state.get("run_id", "run-001")
    candidate_id = geo_result.candidate_id if hasattr(geo_result, "candidate_id") else "AC-001"
    mission_id = f"M-{hashlib.md5(run_id.encode()).hexdigest()[:8]}"

    out_dir = config.get_run_dir(run_id) / "aerodynamics_output"
    out_dir.mkdir(parents=True, exist_ok=True)

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
            vsp3_file_path=geo_result.geometry_artifacts.vsp3_file_path
        ),
        analysis_config=AeroAnalysisConfig(
            analysis_backend="openvsp_vspaero",
            analysis_fidelity="low",
            run_mass_properties=True,
            run_vspaero=True # Enabled to run VSPAERO and extract load distributions
        ),
        output_directory=str(out_dir)
    )
    
    # We pass the request directly via dict to run() matching BaseAIAgent expectations
    print(f"\n[AerodynamicsAnalysisAgent] Executing aerodynamics analysis pipeline (Candidate: {candidate_id}, Backend: {req.analysis_config.analysis_backend})...")
    res = analysis_agent.run({"analysis_request": req})
    
    # Extract the result and return state updates
    analysis_result = res.get("analysis_result")
    if not analysis_result:
        return {"status": "error", "feedback_history": ["Analysis failed to return a result."]}
        
    # We can pass success back or error back. The orchestrator agent handles cyclic routing.
    err_msg = analysis_result.errors[0].message if getattr(analysis_result, "errors", None) else "Unknown error"
    return {
        "analysis_result": analysis_result,
        "status": "error" if analysis_result.status == "failed" else "running",
        "feedback_history": [f"Simulation failed: {err_msg}"] if analysis_result.status == "failed" else []
    }

def orchestrator_node(state: WorkflowState):
    return orchestrator_agent(state)

def route_from_orchestrator(state: WorkflowState):
    return orchestrator_agent.route_edge(state)

def human_node(state: WorkflowState):
    from langgraph.types import interrupt
    full_auto = state.get("full_auto", False)
    awaiting_from = state.get("awaiting_input_from")
    
    print(f"\n[HumanNode] Awaiting input for: {awaiting_from}")
    
    if full_auto:
        print("[HumanNode] Full-auto mode active. Simulating user response...")
        if awaiting_from == "mission_parsing":
            user_reply = "skip"
        elif awaiting_from == "requirement_reasoning":
            user_reply = "auto"
        else:
            user_reply = "continue"
    else:
        # Build payload for interrupt
        missing_fields = []
        if awaiting_from == "mission_parsing" and state.get("mission_parsing_result"):
            missing_fields = [mf.model_dump() for mf in state["mission_parsing_result"].missing_fields]
        unresolved = []
        if awaiting_from == "requirement_reasoning":
            unresolved = state.get("unresolved_questions", [])
            
        interrupt_payload = {
            "type": "needs_human_input",
            "awaiting_from": awaiting_from,
            "missing_fields": missing_fields,
            "unresolved_questions": unresolved
        }
        
        # Pause execution using LangGraph 1.2.0 interrupt
        print(f"\n[HumanNode] Suspending graph execution for HITL...")
        user_reply = interrupt(interrupt_payload)
        
    return {
        "human_input": user_reply,
        "status": "running"
    }

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
    workflow.add_node("human_node", human_node)
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
    workflow.add_edge("human_node", "orchestrator")
    
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
            "human_node": "human_node",
            "END": END
        }
    )
    
    from langgraph.checkpoint.memory import MemorySaver
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
