"""
One-time script to register the MissionParsingAgent's default prompt into Langfuse.
Run with: conda run -n aero python scripts/register_prompts.py
"""

import sys
sys.path.insert(0, "src")

from langfuse import Langfuse
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent

def main():
    # Pull the prompt text directly from the agent
    agent = MissionParsingAgent()
    prompt_text = agent._build_default_prompt().strip()

    client = Langfuse()

    print("Registering prompt 'aeroloop/mission-parsing-agent' to Langfuse...")
    client.create_prompt(
        name="aeroloop/mission-parsing-agent",
        prompt=prompt_text,
        labels=["staging"],
        config={
            "model": "gpt-4o-mini",
            "temperature": 0.0,
        },
    )
    print("Done! Prompt registered with label 'staging'.")

if __name__ == "__main__":
    main()
