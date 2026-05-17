"""
One-time script to register AeroLoop's default agent prompts into Langfuse.
Run with: conda run -n aero python scripts/register_prompts.py
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Callable

sys.path.insert(0, "src")

from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent


@dataclass(frozen=True)
class PromptRegistration:
    name: str
    agent_factory: Callable[[], object]
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


PROMPT_REGISTRATIONS = (
    PromptRegistration(
        name="aeroloop/mission-parsing-agent",
        agent_factory=MissionParsingAgent,
    ),
    PromptRegistration(
        name="aeroloop/customer-requirement-agent",
        agent_factory=CustomerRequirementAgent,
    ),
)


def build_prompt_payload(registration: PromptRegistration, label: str) -> dict:
    agent = registration.agent_factory()
    prompt_text = agent._build_default_prompt().strip()

    return {
        "name": registration.name,
        "prompt": prompt_text,
        "labels": [label],
        "config": {
            "model": registration.model,
            "temperature": registration.temperature,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Register default AeroLoop prompts in Langfuse.")
    parser.add_argument("--label", default="staging", help="Langfuse label to attach to each prompt.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompts that would be registered without calling Langfuse.",
    )
    args = parser.parse_args()

    if args.dry_run:
        client = None
    else:
        from langfuse import Langfuse

        client = Langfuse()

    for registration in PROMPT_REGISTRATIONS:
        payload = build_prompt_payload(registration, args.label)
        print(f"Registering prompt '{payload['name']}' to Langfuse with label '{args.label}'...")

        if args.dry_run:
            print(f"  Prompt length: {len(payload['prompt'])} characters")
            continue

        client.create_prompt(**payload)

    print("Done.")


if __name__ == "__main__":
    main()
