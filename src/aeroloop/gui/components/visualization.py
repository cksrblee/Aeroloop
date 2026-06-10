import os
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Tuple, List

def create_empty_figure(title: str = "No Data") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text="Awaiting Data...", xref="paper", yref="paper", showarrow=False, font=dict(size=20))]
    )
    return fig

def plot_aerodynamics_polar(polar_file_path: str) -> go.Figure:
    """Reads VSPAERO .polar file and plots L/D and Cl vs AoA."""
    if not os.path.exists(polar_file_path):
        return create_empty_figure("Aerodynamic Polar Data")
        
    try:
        # VSPAERO polars typically have header lines, we skip them
        # Let's read lines to find where data starts
        with open(polar_file_path, "r") as f:
            lines = f.readlines()
            
        start_idx = 0
        for i, line in enumerate(lines):
            if "Beta" in line and "AoA" in line and "Mach" in line:
                start_idx = i
                break
                
        df = pd.read_csv(polar_file_path, delim_whitespace=True, skiprows=start_idx)
        
        if df.empty or 'AoA' not in df.columns:
            return create_empty_figure("Empty or Invalid Polar Data")
            
        fig = go.Figure()
        
        # Lift vs AoA
        if 'CLtot' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['AoA'], y=df['CLtot'],
                mode='lines+markers', name='CL',
                line=dict(color='#00ffcc', width=2)
            ))
            
        # Lift to Drag vs AoA
        if 'L/D' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['AoA'], y=df['L/D'],
                mode='lines+markers', name='L/D',
                yaxis='y2',
                line=dict(color='#ff00ff', width=2)
            ))
            
        fig.update_layout(
            title="Aerodynamic Performance (VSPAERO)",
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Angle of Attack (deg)"),
            yaxis=dict(title="Lift Coefficient (CL)", color="#00ffcc"),
            yaxis2=dict(title="Lift-to-Drag Ratio (L/D)", color="#ff00ff", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99)
        )
        return fig
    except Exception as e:
        print(f"Error parsing polar: {e}")
        return create_empty_figure(f"Error Loading Polar: {e}")

def plot_geometry_areas(comp_geom_csv_path: str) -> go.Figure:
    """Reads CompGeom.csv and plots wetted areas."""
    if not os.path.exists(comp_geom_csv_path):
        return create_empty_figure("Component Areas")
        
    try:
        df = pd.read_csv(comp_geom_csv_path)
        # Filter rows where Name exists and is not empty, and not 'Totals' or empty
        # In VSP, CompGeom CSV has multiple sections. The first section has Name, Theo_Area, Wet_Area
        # We can read just the first section.
        
        with open(comp_geom_csv_path, 'r') as f:
            lines = f.readlines()
            
        data = []
        for line in lines[1:]:
            if line.strip() == "":
                break # End of first section
            parts = line.strip().split(',')
            if len(parts) >= 3 and parts[0] != "Totals":
                data.append({"Component": parts[0], "Wet_Area": float(parts[2])})
                
        df_areas = pd.DataFrame(data)
        
        fig = go.Figure(data=[
            go.Bar(name='Wetted Area', x=df_areas['Component'], y=df_areas['Wet_Area'], marker_color='#0088ff')
        ])
        
        fig.update_layout(
            title="Aircraft Component Wetted Areas",
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Component",
            yaxis_title="Area (m^2)"
        )
        return fig
    except Exception as e:
        print(f"Error parsing geometry CSV: {e}")
        return create_empty_figure(f"Error Loading Geometry Data: {e}")
