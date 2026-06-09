from typing import Dict, Any, Optional
from aeroloop.schemas.aerodynamics import MassPropertiesResult

def run_mass_properties(vsp, num_slices: int = 100) -> MassPropertiesResult:
    """
    Executes the OpenVSP mass properties analysis and returns a parsed result.
    """
    mass_result = MassPropertiesResult(mass_analysis_available=False)
    
    try:
        # Compute Mass Properties (Set=0, NumSlices=num_slices, SliceDir=0:X-dir typically)
        vsp.ComputeMassProps(0, num_slices, 0)
        results = vsp.FindLatestResultsID("Mass_Properties")
        
        if results:
            try:
                cg_x = vsp.GetDoubleResults(results, "CG_X")[0]
                cg_y = vsp.GetDoubleResults(results, "CG_Y")[0]
                cg_z = vsp.GetDoubleResults(results, "CG_Z")[0]
                
                mass = vsp.GetDoubleResults(results, "Total_Mass")[0] if "Total_Mass" in vsp.GetAllDataNames(results) else 0.0
                
                ixx = vsp.GetDoubleResults(results, "Ixx")[0] if "Ixx" in vsp.GetAllDataNames(results) else 0.0
                iyy = vsp.GetDoubleResults(results, "Iyy")[0] if "Iyy" in vsp.GetAllDataNames(results) else 0.0
                izz = vsp.GetDoubleResults(results, "Izz")[0] if "Izz" in vsp.GetAllDataNames(results) else 0.0
                
                mass_result.total_mass_kg = mass
                mass_result.center_of_gravity_m = (cg_x, cg_y, cg_z)
                mass_result.moments_of_inertia_kg_m2 = {
                    "ixx": ixx,
                    "iyy": iyy,
                    "izz": izz
                }
                mass_result.mass_analysis_available = True
                
            except Exception as e:
                mass_result.warnings.append(f"Failed to extract some mass properties: {e}")
        else:
            mass_result.warnings.append("Mass_Properties result not found.")
            
    except Exception as e:
        mass_result.warnings.append(f"Error during mass properties computation: {e}")
        
    return mass_result
