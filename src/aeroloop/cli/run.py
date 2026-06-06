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

# Path to the demo requirements file (relative to working directory)
DEMO_FILE = Path("demo_requirements.md")

def init_adapter():
    """Initialize the OpenAI Adapter with standard configuration."""
    # The adapter will pick up OPENAI_API_KEY from environment variables automatically
    return OpenAIAdapter(model_name="gpt-5.4-mini", temperature=0.0)

def ensure_agents_dir():
    """Ensure the .agents/ output directory exists."""
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

        agents_dir = ensure_agents_dir()
        output_file = agents_dir / f"mission_parsing_result_{mission_input.mission_id}.json"

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
        
        agents_dir = ensure_agents_dir()
        output_file = agents_dir / f"customer_requirements_result_{result.mission_id}.json"
        
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
        
        agents_dir = ensure_agents_dir()
        output_file = agents_dir / f"certification_compliance_result_{result.mission_id}.json"
        
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
        # We use recursion_limit to prevent infinite loops during bidirectional routing
        config = {"recursion_limit": 20}
        for s in app.stream(initial_state, config=config):
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
        help="Path to the JSON file containing the parsed MissionProfile (e.g. .agents/mission_parsing_result_xxx.json)"
    )

    # CertificationComplianceAgent subparser
    certification_parser = subparsers.add_parser("certification", help="Run the CertificationComplianceAgent")
    certification_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the CustomerRequirementResult (e.g. .agents/customer_requirements_result_xxx.json)"
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
    elif args.agent == "workflow":
        run_workflow(args)
    else:
        print(f"Unknown agent: {args.agent}")

if __name__ == "__main__":
    main()

