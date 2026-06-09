import sys
import os
sys.path.append(os.path.abspath('src'))
from aeroloop.orchestration.workflow import create_workflow

graph = create_workflow()

# 1. Generate mermaid text
mermaid_text = graph.get_graph().draw_mermaid()
with open("workflow_graph.mmd", "w") as f:
    f.write(mermaid_text)

# 2. Render with mermaid-cli at high resolution
print("Rendering high resolution graph with mermaid-cli...")
# scale factor of 4 (or higher) to improve resolution
os.system("npx -y @mermaid-js/mermaid-cli -i workflow_graph.mmd -o workflow_graph.png -s 4 -b white -p puppeteer-config.json")
print("High resolution graph saved to workflow_graph.png")

