import gradio as gr
import uuid
import os
import pandas as pd
from datetime import datetime
from langgraph.types import Command

from aeroloop.orchestration.workflow import create_workflow
from aeroloop.schemas.mission import MissionParsingInput
from aeroloop.config import config
from aeroloop.gui.components.tracing import format_trace_event
from aeroloop.gui.components.visualization import plot_aerodynamics_polar, plot_geometry_areas

def run_workflow_stream(mission_text: str, full_auto: bool):
    """Generator to run the workflow and yield Gradio UI updates."""
    if not mission_text.strip():
        yield ("Error: Mission text cannot be empty.", "", gr.update(), gr.update(), gr.update())
        return

    # 1. Initialize LangGraph Workflow
    app = create_workflow()
    
    run_id = f"RUN-{uuid.uuid4().hex[:8]}"
    initial_state = {
        "run_id": run_id,
        "raw_input": MissionParsingInput(
            mission_id=f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            raw_user_input=mission_text
        ),
        "mission_profile": None,
        "status": "running",
        "full_auto": full_auto
    }
    
    graph_config = {
        "configurable": {"thread_id": f"gui_run_{run_id}"},
        "recursion_limit": config.max_workflow_iterations
    }
    
    stream_input = initial_state
    trace_log = f"--- Starting Workflow Run: {run_id} ---\n"
    conflict_msg = "All Systems Nominal."
    
    # 2. Stream events
    try:
        while True:
            for s in app.stream(stream_input, config=graph_config):
                # Format tracing event
                new_trace = format_trace_event(s)
                if new_trace:
                    trace_log += new_trace + "\n"
                
                # Yield intermediate state
                yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)
                
            # Check for interrupts
            state_snapshot = app.get_state(graph_config)
            if state_snapshot.tasks and state_snapshot.tasks[0].interrupts:
                interrupt_payload = state_snapshot.tasks[0].interrupts[0].value
                conflict_lines = [f"[HITL Required: {interrupt_payload.get('awaiting_from')}]"]
                
                if interrupt_payload.get("missing_fields"):
                    conflict_lines.append("Missing Information:")
                    for mf in interrupt_payload.get("missing_fields", []):
                        conflict_lines.append(f"  - {mf.get('field_name')}: {mf.get('suggested_question')}")
                        
                if interrupt_payload.get("unresolved_questions"):
                    conflict_lines.append("Unresolved Questions:")
                    for q in interrupt_payload.get("unresolved_questions", []):
                        conflict_lines.append(f"  - {q}")
                
                conflict_msg = "\n".join(conflict_lines)
                trace_log += f"\n>> Graph Paused for Human-in-the-Loop ({interrupt_payload.get('awaiting_from')})\n"
                yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)
                return # Stop generator, wait for user input
            else:
                break
                
        final_status = state_snapshot.values.get("status", "unknown") if hasattr(state_snapshot, "values") else "unknown"
        trace_log += f"\n--- Workflow Finished (Status: {final_status}) ---\n"
        conflict_msg = "Workflow Complete."
        
        # Load visualizations if available
        polar_path = config.get_run_dir(run_id) / "aerodynamics_output" / "Unnamed.polar"
        csv_path = config.get_run_dir(run_id) / "geometry_output" / "Unnamed_CompGeom.csv"
        
        fig_polar = plot_aerodynamics_polar(str(polar_path))
        fig_geo = plot_geometry_areas(str(csv_path))
        
        yield (trace_log, conflict_msg, fig_polar, fig_geo, run_id)
        
    except Exception as e:
        trace_log += f"\n[ERROR] Workflow failed: {e}\n"
        conflict_msg = f"Critical Error: {e}"
        yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)

def provide_hitl_input(user_reply: str, run_id: str, current_trace: str):
    """Resume the workflow from a HITL interrupt."""
    if not user_reply.strip():
        yield (current_trace, "Error: User reply empty.", gr.update(), gr.update(), run_id)
        return
        
    if not run_id:
        yield (current_trace, "Error: No active run_id.", gr.update(), gr.update(), run_id)
        return
        
    app = create_workflow()
    graph_config = {
        "configurable": {"thread_id": f"gui_run_{run_id}"},
        "recursion_limit": config.max_workflow_iterations
    }
    
    stream_input = Command(resume=user_reply)
    trace_log = current_trace + f"\n>> User Input Provided: {user_reply}\n"
    conflict_msg = "Resuming Workflow..."
    
    yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)
    
    # Run the rest
    try:
        while True:
            for s in app.stream(stream_input, config=graph_config):
                new_trace = format_trace_event(s)
                if new_trace:
                    trace_log += new_trace + "\n"
                yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)
                
            state_snapshot = app.get_state(graph_config)
            if state_snapshot.tasks and state_snapshot.tasks[0].interrupts:
                interrupt_payload = state_snapshot.tasks[0].interrupts[0].value
                conflict_lines = [f"[HITL Required: {interrupt_payload.get('awaiting_from')}]"]
                if interrupt_payload.get("unresolved_questions"):
                    for q in interrupt_payload.get("unresolved_questions", []):
                        conflict_lines.append(f"  - {q}")
                conflict_msg = "\n".join(conflict_lines)
                trace_log += f"\n>> Graph Paused for Human-in-the-Loop ({interrupt_payload.get('awaiting_from')})\n"
                yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)
                return
            else:
                break
                
        final_status = state_snapshot.values.get("status", "unknown") if hasattr(state_snapshot, "values") else "unknown"
        trace_log += f"\n--- Workflow Finished (Status: {final_status}) ---\n"
        conflict_msg = "Workflow Complete."
        
        # Load visualizations if available
        polar_path = config.get_run_dir(run_id) / "aerodynamics_output" / "Unnamed.polar"
        csv_path = config.get_run_dir(run_id) / "geometry_output" / "Unnamed_CompGeom.csv"
        
        fig_polar = plot_aerodynamics_polar(str(polar_path))
        fig_geo = plot_geometry_areas(str(csv_path))
        
        yield (trace_log, conflict_msg, fig_polar, fig_geo, run_id)
        
    except Exception as e:
        trace_log += f"\n[ERROR] Workflow failed: {e}\n"
        conflict_msg = f"Critical Error: {e}"
        yield (trace_log, conflict_msg, gr.update(), gr.update(), run_id)


def build_app() -> gr.Blocks:
    # Use a dark, highly contrasted theme
    theme = gr.themes.Monochrome(
        primary_hue="blue", 
        secondary_hue="blue", 
        neutral_hue="slate"
    )
    
    with gr.Blocks(theme=theme, title="AeroLoop Palantir Dashboard") as demo:
        gr.Markdown("# 🚀 AeroLoop Dashboard\n*Palantir-style Agentic Concept Design Environment*")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Input Panel
                gr.Markdown("### Mission Intent Input")
                mission_input = gr.Textbox(
                    lines=5, 
                    placeholder="Enter mission requirements (e.g., An eVTOL for urban transport carrying 4 passengers over 50km...)",
                    label="Mission Description"
                )
                full_auto_cb = gr.Checkbox(label="Full Auto Mode (No HITL interruptions)", value=False)
                start_btn = gr.Button("▶ Execute Mission", variant="primary")
                
                gr.Markdown("### HITL Conflict Resolution")
                conflict_box = gr.Textbox(lines=4, label="Status / Unresolved Conflicts", interactive=False)
                hitl_input = gr.Textbox(lines=2, placeholder="Type response here or 'skip'...", label="User Reply")
                hitl_btn = gr.Button("Submit Reply")
                
                # Hidden state for run_id
                current_run_id = gr.State("")
                
            with gr.Column(scale=2):
                gr.Markdown("### Agent Tracing Telemetry")
                trace_log = gr.TextArea(
                    lines=15, 
                    label="Live Graph Execution", 
                    interactive=False,
                    elem_id="tracing-box"
                )
                
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Aerodynamics Visualizer")
                aero_plot = gr.Plot(label="Aerodynamics")
            with gr.Column():
                gr.Markdown("### Geometry Visualizer")
                geo_plot = gr.Plot(label="Wetted Areas")
                
        # Wiring
        start_btn.click(
            fn=run_workflow_stream,
            inputs=[mission_input, full_auto_cb],
            outputs=[trace_log, conflict_box, aero_plot, geo_plot, current_run_id]
        )
        
        hitl_btn.click(
            fn=provide_hitl_input,
            inputs=[hitl_input, current_run_id, trace_log],
            outputs=[trace_log, conflict_box, aero_plot, geo_plot, current_run_id]
        )
        
    return demo

if __name__ == "__main__":
    app = build_app()
    app.launch(share=False)
