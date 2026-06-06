import sys
import os
sys.path.append(os.path.abspath('src'))
from aeroloop.orchestration.workflow import create_workflow

graph = create_workflow()
png_bytes = graph.get_graph().draw_mermaid_png()
with open("data/workflow_graph.png", "wb") as f:
    f.write(png_bytes)
print("Graph saved to data/workflow_graph.png")
