import os
import sys
import json
from pathlib import Path

# Add OpenVSP to sys.path
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')

from aeroloop.agents.sizing_agent import SizingAgent
from aeroloop.agents.geometry_design_agent import GeometryDesignAgent
from aeroloop.schemas.engineering import SizingRequest, SizingConfig
from aeroloop.schemas.geometry import GeometryDesignRequest, GeometryValidationOptions
from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.aircraft import AircraftCandidate, ConceptBaseline

def test_sizing_to_gda():
    print("--- SIZING TO GDA TEST ---")
    
    # 1. Setup mock mission and baseline
    mission = MissionProfile(
        mission_id="TEST-MISSION-1",
        passenger_count=4,
        mission_distance_m=10000.0,
    )
    
    baseline = ConceptBaseline(
        concept_id="AC-TEST-1",
        aircraft_type="lift_cruise",
        max_length_m=15.0,
        max_wingspan_m=12.0,
        fuselage_width_m_target=1.8,
        fuselage_height_m_target=2.0,
        target_rotor_count=8
    )
    
    candidate = AircraftCandidate(
        candidate_id="AC-TEST-1",
        aircraft_type="lift_cruise_vtol",
        passenger_capacity=4
    )
    
    sizing_req = SizingRequest(
        sizing_request_id="SIZ-REQ-1",
        run_id="RUN-TEST-1",
        mission_id="TEST-MISSION-1",
        candidate_id="AC-TEST-1",
        mission_profile=mission,
        concept_baseline=baseline,
        aircraft_candidate=candidate,
        sizing_config=SizingConfig(allow_template_fallback=True),
        final_requirements=[]
    )
    
    print("1. Running SizingAgent...")
    sizing_agent = SizingAgent()
    sizing_result = sizing_agent.size(sizing_req)
    
    if sizing_result.status != "success" and sizing_result.status != "success_with_warnings":
        print(f"Sizing Failed! Status: {sizing_result.status}")
        print(f"Warnings: {sizing_result.warnings}")
        print(f"Conflict Report: {sizing_result.conflict_report}")
        return
        
    print(f"Sizing Succeeded! MTOW: {sizing_result.sizing_result.mtow_kg:.1f} kg")
    geo_params = sizing_result.geometry_parameter_set
    print(f"Geometry Extracted: Wingspan={geo_params.wingspan_m:.2f}m, Rotors={geo_params.rotor_count}")
    
    # 2. Setup Geometry Design Request
    out_dir = Path("results/test_gda_output")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    geo_req = GeometryDesignRequest(
        geometry_request_id="GEO-REQ-1",
        run_id="RUN-TEST-1",
        mission_id="TEST-MISSION-1",
        candidate_id="AC-TEST-1",
        configuration_id="CFG-1",
        vehicle_type=geo_params.aircraft_type,
        geometry_template="lift_cruise_vtol_template_v1",
        design_parameters=geo_params.dict(exclude_none=True),
        output_directory=str(out_dir),
        validation_options=GeometryValidationOptions(validate_mesh=True)
    )
    
    print("2. Running GeometryDesignAgent...")
    gda = GeometryDesignAgent()
    geo_result = gda.process_request(geo_req)
    
    if geo_result.status == "failed":
        print(f"GDA Failed!")
        for e in geo_result.errors:
            print(f" - Error: {e.message}")
        return
        
    print(f"GDA Succeeded! Status: {geo_result.status}")
    artifacts = geo_result.geometry_artifacts
    print(f"Artifacts Generated:")
    print(f" - VSP3: {artifacts.vsp3_file_path}")
    print(f" - STL: {artifacts.stl_file_path}")
    print(f" - Manifest: {artifacts.geometry_manifest_path}")

if __name__ == "__main__":
    test_sizing_to_gda()
