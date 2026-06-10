import os
import glob
from typing import Dict, Any, List
from aeroloop.schemas.aerodynamics import AerodynamicCoefficientCase, LoadDistributionCase

def parse_vspaero_results(vsp, sweep_res_id: str, case_prefix: str = "AERO-CASE", cwd: str = ".") -> Dict[str, Any]:
    """
    Parses the results from the OpenVSP Results Manager after VSPAEROSweep.
    Returns aerodynamic coefficients and raw data arrays.
    """
    all_results = vsp.GetAllResultsNames()
    
    parsed_data = {
        "coefficients": [],
        "raw": {},
        "warnings": []
    }
    
    # Extract History Data (CL, CDtot, CMy, etc.)
    # Since we bypassed ExecAnalysis to avoid waitpid hangs, Results Manager might not have VSPAERO_History.
    # We parse the .history file manually from disk.
    history_files = glob.glob(os.path.join(cwd, "*.history"))
    if history_files:
        history_file = max(history_files, key=os.path.getmtime)
        try:
            with open(history_file, 'r') as f:
                lines = f.readlines()
            
            cases = []
            current_case = []
            
            # Look for lines that contain integers in the first column
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    iter_num = int(parts[0])
                    current_case.append(parts)
                except ValueError:
                    if current_case:
                        cases.append(current_case)
                        current_case = []
            if current_case:
                cases.append(current_case)
                
            alpha, mach, cl, cd, cm = [], [], [], [], []
            for case in cases:
                last_row = case[-1] # The converged iteration for this case
                mach.append(float(last_row[1]))
                alpha.append(float(last_row[2]))
                cl.append(float(last_row[6]))
                cd.append(float(last_row[9]))
                cm.append(float(last_row[22]))
                
            # Store raw
            parsed_data["raw"]["Alpha"] = alpha
            parsed_data["raw"]["Mach"] = mach
            parsed_data["raw"]["CL"] = cl
            parsed_data["raw"]["CDtot"] = cd
            parsed_data["raw"]["CMy"] = cm
            
            # Assemble coefficients cases
            for i in range(len(alpha)):
                c = AerodynamicCoefficientCase(
                    case_id=f"{case_prefix}-{i+1}",
                    alpha_deg=alpha[i],
                    beta_deg=0.0,
                    speed_mps=None,
                    altitude_m=None,
                    cl=cl[i] if i < len(cl) else None,
                    cd=cd[i] if i < len(cd) else None,
                    cm=cm[i] if i < len(cm) else None,
                    source="vspaero_result"
                )
                parsed_data["coefficients"].append(c)
                
        except Exception as e:
            parsed_data["warnings"].append(f"Failed to parse manually generated VSPAERO .history file: {e}")
            
    else:
        parsed_data["warnings"].append("No .history file found in working directory.")

    # Optionally extract spanwise load data
    load_id = vsp.FindLatestResultsID("VSPAERO_Load")
    if load_id:
        try:
            cl_load = list(vsp.GetDoubleResults(load_id, "cl", 0))
            parsed_data["raw"]["cl_load"] = cl_load
        except Exception as e:
            parsed_data["warnings"].append(f"Failed to parse VSPAERO_Load: {e}")
            
    # Parse .lod files for LoadDistributionCase
    try:
        lod_files = glob.glob(os.path.join(cwd, "*.lod"))
        if lod_files:
            lod_file = max(lod_files, key=os.path.getmtime)
            with open(lod_file, "r") as f:
                lines = f.readlines()
            
            blocks = []
            current_block = []
            in_block = False
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    if in_block:
                        blocks.append(current_block)
                        current_block = []
                        in_block = False
                    continue
                if parts[0] == "Iter" and "Yavg" in parts:
                    in_block = True
                    continue
                if in_block:
                    try:
                        # Ensure it's a data line (starts with an int)
                        int(parts[0])
                        current_block.append(parts)
                    except ValueError:
                        in_block = False
                        if current_block:
                            blocks.append(current_block)
                            current_block = []
            
            if in_block and current_block:
                blocks.append(current_block)
                
            # Assign blocks to cases
            for i, block in enumerate(blocks):
                if i < len(parsed_data["coefficients"]):
                    load_cases = []
                    # Create one LoadDistributionCase containing all rows (or we could split by component)
                    y_span, chord, cl, cd, cm, area = [], [], [], [], [], []
                    for row in block:
                        if len(row) > 30:
                            y_span.append(float(row[4])) # Yavg
                            chord.append(float(row[8]))  # Chord
                            area.append(float(row[9]))   # dArea
                            cl.append(float(row[11]))    # Cl
                            cd.append(float(row[12]))    # Cd
                            cm.append(float(row[28]))    # Cmx (or Cmy? we'll take Cmy which is index 29)
                    
                    # Cmy is index 29 (30th column)
                    cm_vals = [float(row[29]) for row in block if len(row) > 30]
                            
                    lc = LoadDistributionCase(
                        y_span=y_span,
                        chord=chord,
                        cl=cl,
                        cd=cd,
                        cm=cm_vals,
                        area=area
                    )
                    parsed_data["coefficients"][i].load_distribution = [lc]
    except Exception as e:
        parsed_data["warnings"].append(f"Failed to parse .lod file: {e}")

    return parsed_data
