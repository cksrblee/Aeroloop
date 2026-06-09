from typing import Dict, Any, List
from aeroloop.schemas.aerodynamics import AerodynamicCoefficientCase

def parse_vspaero_results(vsp, sweep_res_id: str, case_prefix: str = "AERO-CASE") -> Dict[str, Any]:
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
    history_id = vsp.FindLatestResultsID("VSPAERO_History")
    if history_id:
        data_names = vsp.GetAllDataNames(history_id)
        
        # Typically History contains Alpha, Beta, Mach, CL, CDtot, CMy, etc.
        # Note: Depending on OpenVSP version, polar might be in VSPAERO_Polar.
        # We will check VSPAERO_Polar first if available, else fallback to History for final values.
        
        source_id = history_id
        polar_id = vsp.FindLatestResultsID("VSPAERO_Polar")
        if polar_id:
            source_id = polar_id
            data_names = vsp.GetAllDataNames(polar_id)
            
        try:
            alpha = list(vsp.GetDoubleResults(source_id, "Alpha", 0)) if "Alpha" in data_names else []
            mach = list(vsp.GetDoubleResults(source_id, "Mach", 0)) if "Mach" in data_names else []
            cl = list(vsp.GetDoubleResults(source_id, "CL", 0)) if "CL" in data_names else []
            cd = list(vsp.GetDoubleResults(source_id, "CDtot", 0)) if "CDtot" in data_names else []
            cm = list(vsp.GetDoubleResults(source_id, "CMy", 0)) if "CMy" in data_names else []
            
            # Store raw
            parsed_data["raw"]["Alpha"] = alpha
            parsed_data["raw"]["Mach"] = mach
            parsed_data["raw"]["CL"] = cl
            parsed_data["raw"]["CDtot"] = cd
            parsed_data["raw"]["CMy"] = cm
            
            # Assemble coefficients cases
            for i in range(len(alpha)):
                case = AerodynamicCoefficientCase(
                    case_id=f"{case_prefix}-{i+1}",
                    alpha_deg=alpha[i],
                    beta_deg=0.0, # Placeholder if beta sweep not parsed
                    speed_mps=None,
                    altitude_m=None,
                    cl=cl[i] if i < len(cl) else None,
                    cd=cd[i] if i < len(cd) else None,
                    cm=cm[i] if i < len(cm) else None,
                    source="vspaero_result"
                )
                parsed_data["coefficients"].append(case)
                
        except Exception as e:
            parsed_data["warnings"].append(f"Failed to parse VSPAERO results: {e}")
            
    else:
        parsed_data["warnings"].append("No VSPAERO_History or VSPAERO_Polar found in Results Manager.")

    # Optionally extract spanwise load data
    load_id = vsp.FindLatestResultsID("VSPAERO_Load")
    if load_id:
        try:
            cl_load = list(vsp.GetDoubleResults(load_id, "cl", 0))
            parsed_data["raw"]["cl_load"] = cl_load
        except Exception as e:
            parsed_data["warnings"].append(f"Failed to parse VSPAERO_Load: {e}")
            
    return parsed_data
