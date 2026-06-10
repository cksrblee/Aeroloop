import os
import sys
import pytest
from unittest.mock import MagicMock

# Mock OpenVSP before it gets imported by the agent
mock_vsp = MagicMock()
mock_vsp.VORTEX_LATTICE = 0
mock_vsp.PANEL = 1

# Mock FindGeomsWithName to return a dummy wing ID
mock_vsp.FindGeomsWithName.return_value = ["DummyWingID"]
mock_vsp.FindGeoms.return_value = ["DummyWingID"]
mock_vsp.GetGeomTypeName.return_value = "Wing"

# Mock ExecAnalysis to return a dummy ID and create mock output files
def mock_exec_analysis(name):
    # If it's a sweep, create mock files
    if "Sweep" in name:
        with open("Unnamed.vspaero", "w") as f:
            f.write("mock vspaero\n")
        with open("Unnamed.lod", "w") as f:
            f.write("Iter         VortexSheet TrailVort     Xavg      Yavg      Zavg     dSpan     SoverB      Chord     dArea    V/Vref      Cl        Cd        Cs       Clo       Cdo       Cso       Cli       Cdi       Csi        Cx        Cy       Cz        Cxo       Cyo       Czo       Cxi       Cyi       Czi       Cmx       Cmy       Cmz      Cmxo      Cmyo      Cmzo      Cmxi      Cmyi      Cmzi     StallFact  IsARotor     Diameter        roverR        RPM         Thrust        Thrusto       Thrusti        Power         Powero        Poweri         Moment       Momento       Momenti         J             CT            CQ            CP           ETAP          CT_h           CQ_h         CP_h          FOM          Angle\n")
            f.write("1             1           1           5.97654   8.10000   0.00000   1.80000   0.10000   1.30000   2.34000   1.00000   0.00000   0.00501   0.00000   0.00000   0.00501   0.00000   0.00000   0.00000   0.00000   0.00501   0.00000   0.00000   0.00501   0.00000   0.00000   0.00000   0.00000   0.00000   0.00000   0.00000  -0.03123   0.00000   0.00000  -0.03123   0.00000   0.00000   0.00000   1.00000          0       0.00000           inf       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000\n")
            f.write("\nIter         VortexSheet TrailVort     Xavg      Yavg      Zavg     dSpan     SoverB      Chord     dArea    V/Vref      Cl        Cd        Cs       Clo       Cdo       Cso       Cli       Cdi       Csi        Cx        Cy       Cz        Cxo       Cyo       Czo       Cxi       Cyi       Czi       Cmx       Cmy       Cmz      Cmxo      Cmyo      Cmzo      Cmxi      Cmyi      Cmzi     StallFact  IsARotor     Diameter        roverR        RPM         Thrust        Thrusto       Thrusti        Power         Powero        Poweri         Moment       Momento       Momenti         J             CT            CQ            CP           ETAP          CT_h           CQ_h         CP_h          FOM          Angle\n")
            f.write("2             1           1           5.97654   8.10000   0.00000   1.80000   0.10000   1.30000   2.34000   1.00000   0.00000   0.00501   0.00000   0.00000   0.00501   0.00000   0.00000   0.00000   0.00000   0.00501   0.00000   0.00000   0.00501   0.00000   0.00000   0.00000   0.00000   0.00000   0.00000   0.00000  -0.03123   0.00000   0.00000  -0.03123   0.00000   0.00000   0.00000   1.00000          0       0.00000           inf       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000       0.00000\n")
    return "dummy_sweep_res"

mock_vsp.ExecAnalysis.side_effect = mock_exec_analysis

# Mock FindLatestResultsID
def mock_find_latest_results(name):
    return f"dummy_{name}_id"
mock_vsp.FindLatestResultsID.side_effect = mock_find_latest_results

mock_vsp.GetIntAnalysisInput.return_value = [0]
mock_vsp.GetDoubleAnalysisInput.return_value = [0.0]
mock_vsp.GetStringAnalysisInput.return_value = [""]

# Mock GetAllDataNames
def mock_get_all_data_names(res_id):
    if "History" in res_id or "Polar" in res_id:
        return ["Alpha", "Mach", "CL", "CDtot", "CMy"]
    if "Mass_Properties" in res_id:
        return ["Total_Mass", "Total_CG", "Total_Ixx", "Total_Iyy", "Total_Izz"]
    return []
mock_vsp.GetAllDataNames.side_effect = mock_get_all_data_names

# Mock GetDoubleResults
def mock_get_double_results(res_id, data_name, *args):
    # Aerodynamics
    if data_name == "Alpha": return [0.0, 5.0]
    if data_name == "Mach": return [0.1, 0.1]
    if data_name == "CL": return [0.2500, 0.6500]
    if data_name == "CDtot": return [0.0150, 0.0350]
    if data_name == "CMy": return [-0.05, -0.15]
    
    # Mass Properties
    if data_name == "Total_Mass": return [1200.5]
    if data_name == "Total_Ixx": return [5000.0]
    if data_name == "Total_Iyy": return [8000.0]
    if data_name == "Total_Izz": return [11000.0]
    
    return [0.0]
mock_vsp.GetDoubleResults.side_effect = mock_get_double_results

# Mock GetVec3dResults
def mock_get_vec3d_results(res_id, data_name, *args):
    class MockVec3d:
        def x(self): return 3.2
        def y(self): return 0.0
        def z(self): return 1.1
    if data_name == "Total_CG":
        return [MockVec3d()]
    return [MockVec3d()]
mock_vsp.GetVec3dResults.side_effect = mock_get_vec3d_results

sys.modules["openvsp"] = mock_vsp

from aeroloop.agents.aerodynamics_analysis_agent import AerodynamicsAnalysisAgent
from aeroloop.schemas.aerodynamics import (
    AerodynamicsAnalysisRequest,
    AircraftCandidate,
    GeometryArtifacts,
    AeroAnalysisConfig
)

@pytest.fixture
def sample_vsp3_path():
    vsp3_path = "/root/projects/AeroLoop/thirdparty/test_aircraft.vsp3"
    # Even if missing, we mock the check to let it run for demonstration
    return vsp3_path

@pytest.fixture
def sample_stl_path():
    return "/root/projects/AeroLoop/thirdparty/test_aircraft.stl"

def test_aerodynamics_analysis_agent(sample_vsp3_path, sample_stl_path, monkeypatch):
    # Bypass os.path.exists for geometry files so we can test the workflow
    monkeypatch.setattr(os.path, "exists", lambda x: True)
    
    agent = AerodynamicsAnalysisAgent()
    
    # Construct a minimal request to test the agent
    request = AerodynamicsAnalysisRequest(
        aero_analysis_request_id="TEST-REQ-001",
        run_id="RUN-TEST",
        mission_id="MISSION-TEST",
        candidate_id="AC-TEST",
        geometry_result_id="GEO-TEST-001",
        aircraft_candidate=AircraftCandidate(
            candidate_id="AC-TEST",
            aircraft_type="small_aircraft",
            template_id="TPL-001"
        ),
        geometry_artifacts=GeometryArtifacts(
            vsp3_file_path=sample_vsp3_path,
            stl_file_path=sample_stl_path
        ),
        analysis_config=AeroAnalysisConfig(
            analysis_backend="openvsp_vspaero",
            analysis_fidelity="low",
            run_vspaero=True,
            run_mass_properties=True,
            angle_of_attack_deg=[0.0, 5.0],
            speed_mps=[25.0],
            mass_property_num_slices=20
        ),
        output_directory="/tmp/aero_test_outputs"
    )

    # Make sure output directory exists
    os.makedirs(request.output_directory, exist_ok=True)

    # Process the request
    result = agent.process_request(request)

    print("\n--- [AERODYNAMICS ANALYSIS RESULTS] ---")
    print(f"Status: {result.status}")
    if result.errors:
        print(f"Errors: {result.errors}")

    # Assertions
    assert result.status in ["success", "success_with_warnings"], f"Agent failed with errors: {result.errors}"
    
    # Check mass properties
    if request.analysis_config.run_mass_properties:
        assert result.mass_properties is not None
        assert result.mass_properties.mass_analysis_available is True
        assert result.mass_properties.total_mass_kg is not None
        print(f"Total Mass: {result.mass_properties.total_mass_kg} kg")
        print(f"CG (X,Y,Z): {result.mass_properties.center_of_gravity_m}")

    # Check VSPAERO results
    if request.analysis_config.run_vspaero:
        assert len(result.aerodynamic_coefficients) > 0, "No aerodynamic coefficients parsed."
        assert result.aerodynamic_summary is not None
        print("Aerodynamic Coefficients:")
        for case in result.aerodynamic_coefficients:
            print(f"  AoA: {case.alpha_deg:5.1f} deg | CL: {case.cl:.4f} | CD: {case.cd:.4f} | CM: {case.cm:.4f}")
            assert case.cd is not None, "CD should not be None."
            if case.load_distribution:
                print(f"  [Load Distribution] Found {len(case.load_distribution)} spanwise cases.")
                for lc in case.load_distribution:
                    print(f"    - Y span: {lc.y_span[:2]}... Cl: {lc.cl[:2]}...")
            else:
                print("  [Load Distribution] Not found.")
            
            
        print(f"Aerodynamic Summary - Min CD: {result.aerodynamic_summary.cd_min}")
        print(f"Aerodynamic Summary - Max L/D: {result.aerodynamic_summary.max_lift_to_drag}")
    print("---------------------------------------\n")

if __name__ == "__main__":
    # Provides a simple way to run the test script directly with `python`
    import unittest.mock
    test_aerodynamics_analysis_agent("/root/projects/AeroLoop/thirdparty/test_aircraft.vsp3", "/root/projects/AeroLoop/thirdparty/test_aircraft.stl", unittest.mock.MagicMock())
