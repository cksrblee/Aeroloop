import sys
import os
sys.path.append(os.path.abspath('src'))
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent

agent = CertificationComplianceAgent()
png_bytes = agent.graph.get_graph().draw_mermaid_png()
with open("data/cert_agent_graph.png", "wb") as f:
    f.write(png_bytes)
print("Internal graph saved to data/cert_agent_graph.png")
