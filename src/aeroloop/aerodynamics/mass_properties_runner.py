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
                all_data_names = vsp.GetAllDataNames(results)
                
                if "Total_CG" in all_data_names:
                    cg_vec = vsp.GetVec3dResults(results, "Total_CG")[0]
                    cg_x = cg_vec.x()
                    cg_y = cg_vec.y()
                    cg_z = cg_vec.z()
                else:
                    cg_x = cg_y = cg_z = 0.0
                
                mass = vsp.GetDoubleResults(results, "Total_Mass")[0] if "Total_Mass" in all_data_names else 0.0
                
                ixx = vsp.GetDoubleResults(results, "Total_Ixx")[0] if "Total_Ixx" in all_data_names else 0.0
                iyy = vsp.GetDoubleResults(results, "Total_Iyy")[0] if "Total_Iyy" in all_data_names else 0.0
                izz = vsp.GetDoubleResults(results, "Total_Izz")[0] if "Total_Izz" in all_data_names else 0.0
                
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
