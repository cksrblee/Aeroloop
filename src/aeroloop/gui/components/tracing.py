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
                range_val = mp.range_requirement_m or mp.mission_distance_m or 0.0
                range_nm = range_val / 1852.0
                log_lines.append(f"  -> Extracted Mission: {mp.mission_type} | Range: {range_nm:.1f}nm")
        
        elif node_name == "customer_requirement":
            if "candidate_requirements" in state_update:
                reqs = state_update["candidate_requirements"]
                log_lines.append(f"  -> Generated {len(reqs)} requirements")
                
        elif node_name == "sizing":
            if "sizing_result" in state_update:
                sr = state_update["sizing_result"]
                mtow = sr.sizing_result.mtow_kg if getattr(sr, "sizing_result", None) else 0.0
                power = sr.power_sizing_result.installed_power_kw if getattr(sr, "power_sizing_result", None) else 0.0
                log_lines.append(f"  -> MTOW: {mtow:.2f} kg | Power: {power:.2f} kW")
                if getattr(sr, "warnings", None):
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
                if getattr(ar, "analysis_artifacts", None) and getattr(ar.analysis_artifacts, "polar_file_path", None):
                    log_lines.append(f"  -> Polar generated at: {ar.analysis_artifacts.polar_file_path}")
                    
        if "feedback_history" in state_update and state_update["feedback_history"]:
            for fb in state_update["feedback_history"]:
                log_lines.append(f"  -> FEEDBACK: {fb}")
                
    return "\n".join(log_lines)
