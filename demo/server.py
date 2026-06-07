import os
import sys
import time
import re
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env vars
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Set OpenVSP path
openvsp_path = os.environ.get("OPENVSP_PYTHON_PATH", "/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp")
if openvsp_path not in sys.path:
    sys.path.insert(0, openvsp_path)

import shutil
from aeroloop.agents.geometry_design_agent import GeometryDesignAgent
from aeroloop.schemas.geometry import GeometryDesignRequest, GeometryExportOptions, GeometryValidationOptions
from aeroloop.agents.aerodynamics_analysis_agent import AerodynamicsAnalysisAgent
from aeroloop.schemas.analysis import AerodynamicsAnalysisRequest

app = FastAPI()

# Mount the public directory for the STL files
public_dir = os.path.join(os.path.dirname(__file__), "public")
out_dir = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(public_dir, exist_ok=True)
os.makedirs(out_dir, exist_ok=True)
app.mount("/public", StaticFiles(directory=public_dir), name="public")

import yaml

# Initial State - Read from YAML template
template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "aeroloop", "design", "openvsp_maximal_geometry_template.yaml")
with open(template_path, "r") as f:
    template_data = yaml.safe_load(f)
    
vsp_state = template_data.get("design_parameters", {})
# Default template flag for the demo UI
vsp_state["template"] = "airplane"

geometry_agent = GeometryDesignAgent()
analysis_agent = AerodynamicsAnalysisAgent()

def generate_geometry():
    timestamp = int(time.time() * 1000)
    candidate_id = f"model_{timestamp}"
    
    req = GeometryDesignRequest(
        geometry_request_id=f"req_{timestamp}",
        run_id="run-demo",
        mission_id="mission-demo",
        candidate_id=candidate_id,
        configuration_id="config-demo",
        vehicle_type="drone" if vsp_state["template"] == "drone" else "fixed_wing",
        geometry_template=vsp_state.get("template", "airplane"),
        parameter_sources=[],
        design_parameters=vsp_state,
        output_directory=out_dir,
        export_options=GeometryExportOptions(export_vsp3=True, export_stl=True),
        validation_options=GeometryValidationOptions(validate_mesh=False)
    )
    
    # Run Agent
    res = geometry_agent.process_request(req)
    if res.status != "failed" and res.geometry_artifacts.stl_file_path:
        # Move STL to public dir
        dest_stl = os.path.join(public_dir, f"{candidate_id}.stl")
        shutil.copy(res.geometry_artifacts.stl_file_path, dest_stl)
        return f"{candidate_id}.stl", res.geometry_artifacts.vsp3_file_path
    else:
        print("Agent failed to generate geometry:", res.errors)
        return None, None

def run_analysis(vsp3_path):
    if not vsp3_path:
        return {"Error": "No geometry generated"}
        
    req = AerodynamicsAnalysisRequest(
        geometry_vsp3_path=vsp3_path,
        analysis_type="mass_props"
    )
    res = analysis_agent.process_request(req)
    
    if res.status == "success":
        return res.metrics
    else:
        return {"Error": res.error}

# Initial Generation
current_stl, current_vsp3 = generate_geometry()

# Define new API models for parameters
class ParametersUpdate(BaseModel):
    parameters: dict

@app.get("/api/parameters")
def get_parameters():
    return {"parameters": vsp_state}

@app.post("/api/parameters")
def update_parameters(req: ParametersUpdate):
    global current_stl, current_vsp3, vsp_state
    
    # Update state
    for k, v in req.parameters.items():
        if k in vsp_state:
            vsp_state[k] = float(v) if isinstance(vsp_state[k], float) else v
            
    # Regenerate geometry
    new_stl, new_vsp3 = generate_geometry()
    if new_stl:
        current_stl = new_stl
        current_vsp3 = new_vsp3
        
    return {"status": "success", "stl_url": f"/public/{current_stl}"}

class ChatRequest(BaseModel):
    message: str

def parse_with_llm(message: str):
    import openai
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
        
    openai.api_key = api_key
    prompt = f"""
    You are an aerospace design assistant. Extract the requested changes to the geometry parameters from the user's message.
    The current parameters are: {vsp_state}.
    Return ONLY a JSON dictionary with the updated values. If a parameter is not mentioned, keep the current value.
    Valid keys: {list(vsp_state.keys())}.
    User message: "{message}"
    JSON:
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        import json
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

def parse_with_regex(message: str):
    # Very simple regex fallback
    updates = {}
    if "스팬" in message or "span" in message.lower():
        match = re.search(r'(스팬|span)[^\d]*(\d+(\.\d+)?)', message.lower())
        if match: updates["span"] = float(match.group(2))
    if "후퇴각" in message or "sweep" in message.lower():
        match = re.search(r'(후퇴각|sweep)[^\d]*(\d+(\.\d+)?)', message.lower())
        if match: updates["sweep"] = float(match.group(2))
    if "루트" in message or "root" in message.lower():
        match = re.search(r'(루트|root)[^\d]*(\d+(\.\d+)?)', message.lower())
        if match: updates["root_chord"] = float(match.group(2))
    if "팁" in message or "tip" in message.lower():
        match = re.search(r'(팁|tip)[^\d]*(\d+(\.\d+)?)', message.lower())
        if match: updates["tip_chord"] = float(match.group(2))
    if "드론" in message or "drone" in message.lower() or "쿼드콥터" in message:
        updates["template"] = "drone"
    if "비행기" in message or "airplane" in message.lower() or "항공기" in message:
        updates["template"] = "airplane"
    if "프로펠러" in message or "prop" in message.lower() or "반경" in message:
        match = re.search(r'(프로펠러|prop|반경)[^\d]*(\d+(\.\d+)?)', message.lower())
        if match: updates["prop_radius"] = float(match.group(2))
    
    # Wing locations
    if "x" in message.lower() or "앞뒤" in message or "전후" in message:
        match = re.search(r'(x|앞|뒤)[^\d-]*(-?\d+(\.\d+)?)', message.lower())
        if match: updates["wing_x"] = float(match.group(2))
    if "z" in message.lower() or "위아래" in message or "상하" in message:
        match = re.search(r'(z|상하|위|아래)[^\d-]*(-?\d+(\.\d+)?)', message.lower())
        if match: updates["wing_z"] = float(match.group(2))
        
    return updates

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    global current_stl, current_vsp3, vsp_state
    
    # Try LLM first
    updates = parse_with_llm(req.message)
    if not updates:
        updates = parse_with_regex(req.message)
        
    # Check if analysis is requested
    analysis_results = None
    if "해석" in req.message or "분석" in req.message or "analyze" in req.message.lower() or "면적" in req.message or "부피" in req.message:
        analysis_results = run_analysis(current_vsp3)
        
    if not updates and not analysis_results:
        return {
            "reply": "명령을 이해하지 못했습니다. (예: '비행기로 바꿔줘', '날개 x 위치 3으로 이동', '면적 해석해줘')",
            "stl_url": f"/public/{current_stl}",
            "parameters": vsp_state,
            "analysis": None
        }
        
    # Update state
    if updates:
        for k, v in updates.items():
            if k in vsp_state:
                vsp_state[k] = float(v) if isinstance(vsp_state[k], float) else v
                
        # Regenerate geometry
        new_stl, new_vsp3 = generate_geometry()
        if new_stl:
            current_stl = new_stl
            current_vsp3 = new_vsp3
    
    # Formulate response
    reply_parts = []
    if updates:
        updated_str = ", ".join([f"{k}: {v}" for k, v in updates.items()])
        reply_parts.append(f"파라미터가 업데이트 되었습니다: {updated_str}.")
    if analysis_results:
        vol = analysis_results.get("Volume", "N/A")
        wet = analysis_results.get("Wetted_Area", "N/A")
        reply_parts.append(f"해석 결과: 부피={vol}, 표면적={wet}.")
        
    reply = " ".join(reply_parts)
    
    return {
        "reply": reply,
        "stl_url": f"/public/{current_stl}",
        "parameters": vsp_state,
        "analysis": analysis_results
    }

@app.get("/")
def read_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
