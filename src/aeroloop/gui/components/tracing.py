import json
from typing import Dict, Any

def format_trace_event(event: Dict[str, Any]) -> str:
    """Formats a LangGraph event into a Palantir-style telemetry log line."""
    log_lines = []
    
    for node_name, state_update in event.items():
        status = state_update.get("status", "completed")
        run_id = state_update.get("run_id", "N/A")
        
        # Color codes or formatting for a dark theme can be raw text if going into a textarea,
        # or HTML if going into a Gradio HTML component. We'll use simple structured text 
        # which Gradio Markdown or Textarea can display cleanly.
        
        timestamp = "[TELEMETRY]"
        node_display = f"[{node_name.upper()}]"
        
        line = f"{timestamp} {node_display} Status: {status.upper()}"
        log_lines.append(line)
        
        # Extra details based on node type
        if node_name == "mission_parsing":
            if "mission_profile" in state_update and state_update["mission_profile"]:
                mp = state_update["mission_profile"]
                log_lines.append(f"  -> Extracted Mission: {mp.mission_type} | Range: {mp.target_range_nm}nm")
        
        elif node_name == "customer_requirement":
            if "candidate_requirements" in state_update:
                reqs = state_update["candidate_requirements"]
                log_lines.append(f"  -> Generated {len(reqs)} requirements")
                
        elif node_name == "sizing":
            if "sizing_result" in state_update:
                sr = state_update["sizing_result"]
                log_lines.append(f"  -> MTOW: {sr.mtow_kg:.2f} kg | Power: {sr.total_power_kw:.2f} kW")
                if sr.warnings:
                    log_lines.append(f"  -> WARNINGS: {', '.join(sr.warnings)}")
                    
        elif node_name == "certification_validator":
            if "certification_validation_result" in state_update:
                cv = state_update["certification_validation_result"]
                log_lines.append(f"  -> Valid: {cv.is_valid}")
                if cv.violations:
                    for v in cv.violations:
                        log_lines.append(f"  -> VIOLATION: {v}")
                        
        elif node_name == "aerodynamics_analysis":
            if "analysis_result" in state_update:
                ar = state_update["analysis_result"]
                log_lines.append(f"  -> Aero Status: {ar.status}")
                if ar.artifacts and ar.artifacts.polar_file_path:
                    log_lines.append(f"  -> Polar generated at: {ar.artifacts.polar_file_path}")
                    
        if "feedback_history" in state_update and state_update["feedback_history"]:
            for fb in state_update["feedback_history"]:
                log_lines.append(f"  -> FEEDBACK: {fb}")
                
    return "\n".join(log_lines)
