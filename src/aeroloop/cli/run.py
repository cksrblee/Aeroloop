import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from aeroloop.llm.adapters import OpenAIAdapter
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.schemas.mission import MissionParsingInput

# Path to the demo requirements file (relative to working directory)
DEMO_FILE = Path("demo_requirements.md")

def init_adapter():
    """Initialize the OpenAI Adapter with standard configuration."""
    # The adapter will pick up OPENAI_API_KEY from environment variables automatically
    return OpenAIAdapter(model_name="gpt-4o-mini", temperature=0.0)

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

    args = parser.parse_args()

    if args.agent == "mission":
        run_mission_agent(args)
    else:
        print(f"Unknown agent: {args.agent}")

if __name__ == "__main__":
    main()

