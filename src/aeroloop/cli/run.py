import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from aeroloop.llm.adapters import OpenAIAdapter
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.schemas.mission import MissionParsingInput, MissionProfile, MissionParsingResult
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent
from aeroloop.schemas.compliance import CertificationComplianceInput
from aeroloop.schemas.certification import CertificationSourcePolicy
from aeroloop.config import config

# Path to the demo requirements file (relative to working directory)
DEMO_FILE = Path("demo_requirements.md")

def init_adapter():
    """Initialize the OpenAI Adapter with standard configuration."""
    # The adapter will pick up OPENAI_API_KEY from environment variables automatically
    return OpenAIAdapter(model_name="gpt-5.4-mini", temperature=0.0)

def ensure_agents_dir():
    """Ensure the legacy .agents/ output directory exists (used for fallbacks)."""
    agents_dir = Path(".agents")
    agents_dir.mkdir(exist_ok=True)
    return agents_dir

def load_mission_text(text_arg: str) -> str:
    """
    Returns the raw mission text.
    If the argument is 'demo', loads from demo_requirements.md.
    """
    if text_arg.strip().lower() == "demo":
        if not DEMO_FILE.exists():
            raise FileNotFoundError(
                f"Demo file not found: {DEMO_FILE.absolute()}\n"
                "Make sure 'demo_requirements.md' exists in the current directory."
            )
        content = DEMO_FILE.read_text(encoding="utf-8")
        print(f"Loaded demo input from: {DEMO_FILE.absolute()}")
        return content
    return text_arg

def run_mission_agent(args):
    """Run the MissionParsingAgent on the provided text (or demo file)."""
    print("Initializing OpenAI Adapter...")
    adapter = init_adapter()

    print("Initializing MissionParsingAgent...")
    agent = MissionParsingAgent(llm_model=adapter)

    # Resolve demo or literal text
    raw_text = load_mission_text(args.text)

    mission_input = MissionParsingInput(
        mission_id=f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        raw_user_input=raw_text
    )

    print("\n--- Running MissionParsingAgent ---")
    try:
        result = agent.parse(mission_input)

        run_dir = config.get_run_dir(mission_input.mission_id)
        output_file = run_dir / f"mission_parsing_result.json"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Mission parsing completed.")
        print(f"Output saved to: {output_file.absolute()}")

        # Print a short summary to the console
        print("\n--- Summary ---")
        print(f"Mission ID         : {result.mission_id}")
        profile = result.mission_profile
        print(f"Operation Area     : {profile.operation_area}")
        print(f"Origin → Dest      : {profile.origin} → {profile.destination}")
        print(f"Vehicle Hint       : {profile.vehicle_type_hint}")
        print(f"Passenger Count    : {profile.passenger_count}")
        print(f"Max Altitude (m)   : {profile.max_altitude_m}")
        print(f"Explicit Constraints    : {len(result.explicit_constraints)}")
        print(f"Implicit Candidates     : {len(result.implicit_constraint_candidates)}")
        print(f"Requirement Seeds       : {len(result.requirement_seed_candidates)}")
        print(f"Runtime Monitor Vars    : {len(result.runtime_monitoring_candidates)}")
        print(f"Missing Fields          : {len(result.missing_fields)}")
        print(f"Ambiguities             : {len(result.ambiguities)}")
        if result.confidence_summary:
            print(f"Overall Confidence      : {result.confidence_summary.overall_confidence:.2f}")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        print(f"\n[ERROR] MissionParsingAgent failed: {e}")
        raise

def run_customer_agent(args):
    """Run the CustomerRequirementAgent on a previously parsed MissionProfile JSON file."""
    print("Initializing CustomerRequirementAgent...")
    agent = CustomerRequirementAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading parsed mission from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # We expect a MissionParsingResult JSON here
        parsing_result = MissionParsingResult(**data)
        mission_profile = parsing_result.mission_profile
        mission_id_str = parsing_result.mission_id
    except Exception as e:
        print(f"\n[ERROR] Failed to load MissionProfile from {input_file.name}: {e}")
        return

    print("\n--- Running CustomerRequirementAgent ---")
    try:
        result = agent.analyze(mission_profile, mission_id=mission_id_str)
        
        run_dir = config.get_run_dir(result.mission_id)
        output_file = run_dir / f"customer_requirements_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Customer Requirement generation completed.")
        print(f"Output saved to: {output_file.absolute()}")

        # Print a short summary
        print("\n--- Summary ---")
        print(f"Mission ID                 : {result.mission_id}")
        print(f"Candidate Requirements     : {len(result.candidate_requirements)}")
        print(f"Assumptions                : {len(result.assumptions)}")
        print(f"Unresolved Questions       : {len(result.unresolved_questions)}")
        print(f"Quality Flags              : {len(result.quality_flags)}")
        for req in result.candidate_requirements:
            print(f"  - [{req.category}] {req.title} ({req.requirement_type})")
            
    except Exception as e:
        print(f"\n[ERROR] CustomerRequirementAgent failed: {e}")
        raise

def run_certification_agent(args):
    """Run the CertificationComplianceAgent on a previously parsed CustomerRequirementResult."""
    print("Initializing CertificationComplianceAgent...")
    agent = CertificationComplianceAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading customer requirements from: {input_file.absolute()}")
    try:
        from aeroloop.schemas.requirement import CustomerRequirementResult
        from aeroloop.schemas.mission import MissionProfile
        
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = CustomerRequirementResult(**data)
        
        # Attempt to load corresponding MissionProfile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.mission_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile(mission_id=req_result.mission_id)
            
        from aeroloop.schemas.aircraft import AircraftConcept
        concept = AircraftConcept(
            concept_id="eVTOL-CONCEPT-01",
            aircraft_type="evtol",
            mtow_kg=3000.0,
            passenger_count=4,
            propulsion_type="electric",
            number_of_motors=8,
            number_of_lift_units=8,
            has_wing=True,
            vertical_takeoff_landing=True,
            intended_operation="urban_air_mobility"
        )
        
        comp_input = CertificationComplianceInput(
            run_id=req_result.mission_id,
            mission_profile=mission_profile,
            customer_requirements=req_result.candidate_requirements,
            aircraft_concept=concept,
            certification_source_policy=CertificationSourcePolicy(
                allowed_source_families=["SC_VTOL_SMALL", "SMALL_ROTORCRAFT", "SMALL_AIRCRAFT"],
                allowed_authorities=["EASA", "FAA"]
            )
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running CertificationComplianceAgent ---")
    try:
        result = agent.analyze(comp_input)
        
        run_dir = config.get_run_dir(result.mission_id)
        output_file = run_dir / f"certification_compliance_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Certification Compliance generation completed.")
        print(f"Output saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Mission ID                 : {result.mission_id}")
        print(f"CCL Items                  : {len(result.ccl_items)}")
        print(f"MoC Plans                  : {len(result.moc_plans)}")
        print(f"Readiness Level            : {result.quality_report.readiness_level}")
            
    except Exception as e:
        print(f"\n[ERROR] CertificationComplianceAgent failed: {e}")
        raise

def run_reasoning_agent(args):
    """Run the RequirementReasoningAgent on a previously parsed CustomerRequirementResult."""
    print("Initializing RequirementReasoningAgent...")
    print("Initializing OpenAI Adapter...")
    adapter = init_adapter()
    from aeroloop.agents.requirement_reasoning_agent import RequirementReasoningAgent
    agent = RequirementReasoningAgent(llm_model=adapter)
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading customer requirements from: {input_file.absolute()}")
    try:
        from aeroloop.schemas.requirement import CustomerRequirementResult, RequirementReasoningInput
        from aeroloop.schemas.mission import MissionProfile
        
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = CustomerRequirementResult(**data)
        
        # Attempt to load corresponding MissionProfile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.mission_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile(mission_id=req_result.mission_id)
            
        reasoning_input = RequirementReasoningInput(
            run_id=req_result.mission_id,
            mission_profile=mission_profile,
            candidate_requirements=req_result.candidate_requirements,
            unresolved_questions=req_result.unresolved_questions
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running RequirementReasoningAgent ---")
    try:
        result = agent.refine(reasoning_input)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"requirement_reasoning_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        # Also generate the human-readable markdown report (Blueprint)
        report_md = agent.export_markdown_report(reasoning_input, result)
        report_file = run_dir / f"System_Requirements_Report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)

        print(f"\n[SUCCESS] Requirement Reasoning completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")
        print(f"Markdown Report saved to: {report_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Run ID                     : {result.run_id}")
        print(f"Status                     : {result.status}")
        print(f"Final Requirements         : {len(result.final_requirements)}")
        print(f"Resolved Assumptions       : {len(result.resolved_assumptions)}")
        print(f"Remaining Questions (HITL) : {len(result.remaining_unresolved_questions)}")
        for a in result.resolved_assumptions:
            print(f"  - [Assumed {a.assumed_value}] Q: {a.question}")
            
    except Exception as e:
        print(f"\n[ERROR] RequirementReasoningAgent failed: {e}")
        raise

def run_sizing_agent(args):
    """Run the SizingAgent on a previously generated RequirementReasoningResult."""
    print("Initializing SizingAgent...")
    from aeroloop.agents.sizing_agent import SizingAgent
    from aeroloop.schemas.requirement import RequirementReasoningResult
    from aeroloop.schemas.engineering import SizingRequest, SizingConfig
    from aeroloop.schemas.aircraft import AircraftCandidate
    from aeroloop.schemas.mission import MissionProfile
    
    agent = SizingAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading reasoning results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = RequirementReasoningResult(**data)
        
        # Load mission profile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.run_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile()
            
        candidate_id = f"AC-{req_result.run_id[-6:]}"
        candidate = AircraftCandidate(
            candidate_id=candidate_id,
            aircraft_type="lift_cruise_vtol",
            passenger_capacity=mission_profile.passenger_count if hasattr(mission_profile, 'passenger_count') and mission_profile.passenger_count else 4
        )
        
        sizing_req = SizingRequest(
            sizing_request_id=f"REQ-SIZ-{req_result.run_id[-6:]}",
            run_id=req_result.run_id,
            mission_id=req_result.run_id,
            candidate_id=candidate_id,
            mission_profile=mission_profile,
            aircraft_candidate=candidate,
            sizing_config=SizingConfig(),
            final_requirements=req_result.final_requirements
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running SizingAgent ---")
    try:
        result = agent.size(sizing_req)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"sizing_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Sizing completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        if result.sizing_result:
            print(f"MTOW (kg)                  : {result.sizing_result.mtow_kg:.1f}")
        if result.geometry_parameter_set:
            print(f"Wing Area (m2)             : {result.geometry_parameter_set.wing_area_m2}")
            print(f"Total Disk Area (m2)       : {result.geometry_parameter_set.total_disk_area_m2}")
            
    except Exception as e:
        print(f"\n[ERROR] SizingAgent failed: {e}")
        raise

def run_validator_agent(args):
    """Run the CertificationValidatorAgent on a reasoning result and compliance result."""
    print("Initializing CertificationValidatorAgent...")
    from aeroloop.agents.certification_validator_agent import CertificationValidatorAgent
    from aeroloop.schemas.compliance import CertificationValidationInput, CertificationComplianceResult
    from aeroloop.schemas.requirement import RequirementReasoningResult
    
    agent = CertificationValidatorAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading reasoning results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = RequirementReasoningResult(**data)
        
        # Load compliance result
        comp_file = input_file.parent / f"certification_compliance_result.json"
        if not comp_file.exists():
            comp_file = input_file.parent / f"certification_compliance_result_{req_result.run_id}.json"
            
        if not comp_file.exists():
            print(f"\n[ERROR] Certification compliance result not found: {comp_file.absolute()}")
            return
            
        with open(comp_file, "r", encoding="utf-8") as cf:
            c_data = json.load(cf)
            comp_result = CertificationComplianceResult(**c_data)
            
        if not req_result.concept_baseline:
            print("\n[ERROR] ConceptBaseline is missing from RequirementReasoningResult.")
            return
            
        val_input = CertificationValidationInput(
            run_id=req_result.run_id,
            concept_baseline=req_result.concept_baseline,
            compliance_result=comp_result
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs: {e}")
        return

    print("\n--- Running CertificationValidatorAgent ---")
    try:
        result = agent.validate(val_input)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"certification_validation_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Validation completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Is Valid                   : {result.is_valid}")
        print(f"Violations                 : {len(result.violations)}")
        for v in result.violations:
            print(f"  - [VIOLATION] {v}")
        print(f"Warnings                   : {len(result.warnings)}")
        for w in result.warnings:
            print(f"  - [WARNING] {w}")
            
    except Exception as e:
        print(f"\n[ERROR] CertificationValidatorAgent failed: {e}")
        raise

def run_workflow(args):
    """Run the entire bidirectional LangGraph workflow."""
    from aeroloop.orchestration.workflow import create_workflow
    from aeroloop.schemas.mission import MissionParsingInput
    import uuid
    
    print("Initializing LangGraph Workflow...")
    app = create_workflow()
    
    raw_text = load_mission_text(args.text)
    
    initial_state = {
        "run_id": f"RUN-{uuid.uuid4().hex[:8]}",
        "raw_input": MissionParsingInput(
            mission_id=f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            raw_user_input=raw_text
        ),
        "mission_profile": None,
        "status": "running"
    }
    
    print("\n--- Starting Bidirectional Workflow ---")
    try:
        # We use max_workflow_iterations from config to prevent infinite loops during bidirectional routing
        from aeroloop.config import config
        graph_config = {"recursion_limit": config.max_workflow_iterations}
        for s in app.stream(initial_state, config=graph_config):
            node_name = list(s.keys())[0]
            print(f"\n[Node Execution: {node_name}]")
            state_update = s[node_name]
            
            if "status" in state_update:
                print(f"  Status: {state_update['status']}")
            if "next_node" in state_update:
                print(f"  Routing -> {state_update['next_node']}")
            if "feedback_history" in state_update and state_update["feedback_history"]:
                print(f"  Feedback: {state_update['feedback_history'][-1]}")
            
            # Print intermediate results for visibility
            if "candidate_requirements" in state_update and state_update["candidate_requirements"]:
                print(f"  Generated {len(state_update['candidate_requirements'])} candidate requirements.")
        
        print("\n[SUCCESS] Workflow execution completed.")
    except Exception as e:
        print(f"\n[ERROR] Workflow failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="AeroLoop High-Level Agent Execution CLI")
    subparsers = parser.add_subparsers(dest="agent", help="Which agent to run")
    subparsers.required = True

    # MissionParsingAgent subparser
    mission_parser = subparsers.add_parser("mission", help="Run the MissionParsingAgent")
    mission_parser.add_argument(
        "text",
        type=str,
        help=(
            "The natural language mission description to parse. "
            "Pass 'demo' to load from demo_requirements.md."
        )
    )

    # CustomerRequirementAgent subparser
    customer_parser = subparsers.add_parser("customer", help="Run the CustomerRequirementAgent")
    customer_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the parsed MissionProfile (e.g. results/default_user/RUN-XXX/mission_parsing_result.json)"
    )

    # CertificationComplianceAgent subparser
    certification_parser = subparsers.add_parser("certification", help="Run the CertificationComplianceAgent")
    certification_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the CustomerRequirementResult (e.g. results/default_user/RUN-XXX/customer_requirements_result.json)"
    )

    # RequirementReasoningAgent subparser
    reasoning_parser = subparsers.add_parser("reasoning", help="Run the RequirementReasoningAgent")
    reasoning_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the CustomerRequirementResult (e.g. results/default_user/RUN-XXX/customer_requirements_result.json)"
    )

    # SizingAgent subparser
    sizing_parser = subparsers.add_parser("sizing", help="Run the SizingAgent")
    sizing_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the RequirementReasoningResult (e.g. results/default_user/RUN-XXX/requirement_reasoning_result.json)"
    )

    # ValidatorAgent subparser
    validator_parser = subparsers.add_parser("validator", help="Run the CertificationValidatorAgent")
    validator_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the RequirementReasoningResult (e.g. results/default_user/RUN-XXX/requirement_reasoning_result.json)"
    )

    # Workflow subparser
    workflow_parser = subparsers.add_parser("workflow", help="Run the Bidirectional LangGraph Workflow")
    workflow_parser.add_argument(
        "text",
        type=str,
        help="The natural language mission description. Pass 'demo' to load from demo_requirements.md."
    )

    args = parser.parse_args()

    if args.agent == "mission":
        run_mission_agent(args)
    elif args.agent == "customer":
        run_customer_agent(args)
    elif args.agent == "certification":
        run_certification_agent(args)
    elif args.agent == "reasoning":
        run_reasoning_agent(args)
    elif args.agent == "sizing":
        run_sizing_agent(args)
    elif args.agent == "validator":
        run_validator_agent(args)
    elif args.agent == "workflow":
        run_workflow(args)
    else:
        print(f"Unknown agent: {args.agent}")

if __name__ == "__main__":
    main()

