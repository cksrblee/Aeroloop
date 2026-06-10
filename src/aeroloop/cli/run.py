import argparse
import json
import os
import warnings
from pathlib import Path
from datetime import datetime

# Suppress LangGraph msgpack serialization warnings for Pydantic objects
warnings.filterwarnings("ignore", message="Deserializing unregistered type")

from aeroloop.llm.adapters import OpenAIAdapter
from aeroloop.agents.mission_parsing_agent import MissionParsingAgent
from aeroloop.schemas.mission import MissionParsingInput, MissionProfile, MissionParsingResult
from aeroloop.agents.customer_requirement_agent import CustomerRequirementAgent
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent
from aeroloop.schemas.compliance import CertificationComplianceInput
from aeroloop.schemas.certification import CertificationSourcePolicy
from aeroloop.config import config

# Path to the demo requirements file (relative to working directory)
DEMO_FILE = Path("demo_requirements.md")

def init_adapter():
    """Initialize the OpenAI Adapter with standard configuration."""
    # The adapter will pick up OPENAI_API_KEY from environment variables automatically
    return OpenAIAdapter(model_name=config.llm_model_name, temperature=config.llm_temperature)

def ensure_agents_dir():
    """Ensure the legacy .agents/ output directory exists (used for fallbacks)."""
    agents_dir = Path(".agents")
    agents_dir.mkdir(exist_ok=True)
    return agents_dir

def load_mission_text(text_arg: str) -> str:
    """
    Returns the raw mission text.
    If the argument is 'demo', loads from demo_requirements.md.
    """
    if text_arg.strip().lower() == "demo":
        if not DEMO_FILE.exists():
            raise FileNotFoundError(
                f"Demo file not found: {DEMO_FILE.absolute()}\n"
                "Make sure 'demo_requirements.md' exists in the current directory."
            )
        content = DEMO_FILE.read_text(encoding="utf-8")
        print(f"Loaded demo input from: {DEMO_FILE.absolute()}")
        return content
    return text_arg

def run_mission_agent(args):
    """Run the MissionParsingAgent on the provided text (or demo file)."""
    print("Initializing OpenAI Adapter...")
    adapter = init_adapter()

    print("Initializing MissionParsingAgent...")
    agent = MissionParsingAgent(llm_model=adapter)

    # Resolve demo or literal text
    raw_text = load_mission_text(args.text)

    mission_input = MissionParsingInput(
        mission_id=f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        raw_user_input=raw_text
    )

    print("\n--- Running MissionParsingAgent ---")
    try:
        result = agent.parse(mission_input)

        run_dir = config.get_run_dir(mission_input.mission_id)
        output_file = run_dir / f"mission_parsing_result.json"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Mission parsing completed.")
        print(f"Output saved to: {output_file.absolute()}")

        # Print a short summary to the console
        print("\n--- Summary ---")
        print(f"Mission ID         : {result.mission_id}")
        profile = result.mission_profile
        print(f"Operation Area     : {profile.operation_area}")
        print(f"Origin → Dest      : {profile.origin} → {profile.destination}")
        print(f"Vehicle Hint       : {profile.vehicle_type_hint}")
        print(f"Passenger Count    : {profile.passenger_count}")
        print(f"Max Altitude (m)   : {profile.max_altitude_m}")
        print(f"Explicit Constraints    : {len(result.explicit_constraints)}")
        print(f"Implicit Candidates     : {len(result.implicit_constraint_candidates)}")
        print(f"Requirement Seeds       : {len(result.requirement_seed_candidates)}")
        print(f"Runtime Monitor Vars    : {len(result.runtime_monitoring_candidates)}")
        print(f"Missing Fields          : {len(result.missing_fields)}")
        print(f"Ambiguities             : {len(result.ambiguities)}")
        if result.confidence_summary:
            print(f"Overall Confidence      : {result.confidence_summary.overall_confidence:.2f}")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        print(f"\n[ERROR] MissionParsingAgent failed: {e}")
        raise

def run_customer_agent(args):
    """Run the CustomerRequirementAgent on a previously parsed MissionProfile JSON file."""
    print("Initializing CustomerRequirementAgent...")
    agent = CustomerRequirementAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading parsed mission from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # We expect a MissionParsingResult JSON here
        parsing_result = MissionParsingResult(**data)
        mission_profile = parsing_result.mission_profile
        mission_id_str = parsing_result.mission_id
    except Exception as e:
        print(f"\n[ERROR] Failed to load MissionProfile from {input_file.name}: {e}")
        return

    print("\n--- Running CustomerRequirementAgent ---")
    try:
        result = agent.analyze(mission_profile, mission_id=mission_id_str)
        
        run_dir = config.get_run_dir(result.mission_id)
        output_file = run_dir / f"customer_requirements_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Customer Requirement generation completed.")
        print(f"Output saved to: {output_file.absolute()}")

        # Print a short summary
        print("\n--- Summary ---")
        print(f"Mission ID                 : {result.mission_id}")
        print(f"Candidate Requirements     : {len(result.candidate_requirements)}")
        print(f"Assumptions                : {len(result.assumptions)}")
        print(f"Unresolved Questions       : {len(result.unresolved_questions)}")
        print(f"Quality Flags              : {len(result.quality_flags)}")
        for req in result.candidate_requirements:
            print(f"  - [{req.category}] {req.title} ({req.requirement_type})")
            
    except Exception as e:
        print(f"\n[ERROR] CustomerRequirementAgent failed: {e}")
        raise

def run_certification_agent(args):
    """Run the CertificationComplianceAgent on a previously parsed CustomerRequirementResult."""
    print("Initializing CertificationComplianceAgent...")
    agent = CertificationComplianceAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading customer requirements from: {input_file.absolute()}")
    try:
        from aeroloop.schemas.requirement import CustomerRequirementResult
        from aeroloop.schemas.mission import MissionProfile
        
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = CustomerRequirementResult(**data)
        
        # Attempt to load corresponding MissionProfile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.mission_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile(mission_id=req_result.mission_id)
            
        from aeroloop.schemas.aircraft import AircraftConcept
        concept = AircraftConcept(
            concept_id="eVTOL-CONCEPT-01",
            aircraft_type="evtol",
            mtow_kg=3000.0,
            passenger_count=4,
            propulsion_type="electric",
            number_of_motors=8,
            number_of_lift_units=8,
            has_wing=True,
            vertical_takeoff_landing=True,
            intended_operation="urban_air_mobility"
        )
        
        comp_input = CertificationComplianceInput(
            run_id=req_result.mission_id,
            mission_profile=mission_profile,
            customer_requirements=req_result.candidate_requirements,
            aircraft_concept=concept,
            certification_source_policy=CertificationSourcePolicy(
                allowed_source_families=["SC_VTOL_SMALL", "SMALL_ROTORCRAFT", "SMALL_AIRCRAFT"],
                allowed_authorities=["EASA", "FAA"]
            )
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running CertificationComplianceAgent ---")
    try:
        result = agent.analyze(comp_input)
        
        run_dir = config.get_run_dir(result.mission_id)
        output_file = run_dir / f"certification_compliance_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print("\n[SUCCESS] Certification Compliance generation completed.")
        print(f"Output saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Mission ID                 : {result.mission_id}")
        print(f"CCL Items                  : {len(result.ccl_items)}")
        print(f"MoC Plans                  : {len(result.moc_plans)}")
        print(f"Readiness Level            : {result.quality_report.readiness_level}")
            
    except Exception as e:
        print(f"\n[ERROR] CertificationComplianceAgent failed: {e}")
        raise

def run_reasoning_agent(args):
    """Run the RequirementReasoningAgent on a previously parsed CustomerRequirementResult."""
    print("Initializing RequirementReasoningAgent...")
    print("Initializing OpenAI Adapter...")
    adapter = init_adapter()
    from aeroloop.agents.requirement_reasoning_agent import RequirementReasoningAgent
    agent = RequirementReasoningAgent(llm_model=adapter)
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading customer requirements from: {input_file.absolute()}")
    try:
        from aeroloop.schemas.requirement import CustomerRequirementResult, RequirementReasoningInput
        from aeroloop.schemas.mission import MissionProfile
        
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = CustomerRequirementResult(**data)
        
        # Attempt to load corresponding MissionProfile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.mission_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile(mission_id=req_result.mission_id)
            
        reasoning_input = RequirementReasoningInput(
            run_id=req_result.mission_id,
            mission_profile=mission_profile,
            candidate_requirements=req_result.candidate_requirements,
            unresolved_questions=req_result.unresolved_questions
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running RequirementReasoningAgent ---")
    try:
        result = agent.refine(reasoning_input)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"requirement_reasoning_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        # Also generate the human-readable markdown report (Blueprint)
        report_md = agent.export_markdown_report(reasoning_input, result)
        report_file = run_dir / f"System_Requirements_Report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)

        print(f"\n[SUCCESS] Requirement Reasoning completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")
        print(f"Markdown Report saved to: {report_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Run ID                     : {result.run_id}")
        print(f"Status                     : {result.status}")
        print(f"Final Requirements         : {len(result.final_requirements)}")
        print(f"Resolved Assumptions       : {len(result.resolved_assumptions)}")
        print(f"Remaining Questions (HITL) : {len(result.remaining_unresolved_questions)}")
        for a in result.resolved_assumptions:
            print(f"  - [Assumed {a.assumed_value}] Q: {a.question}")
            
    except Exception as e:
        print(f"\n[ERROR] RequirementReasoningAgent failed: {e}")
        raise

def run_sizing_agent(args):
    """Run the SizingAgent on a previously generated RequirementReasoningResult."""
    print("Initializing SizingAgent...")
    from aeroloop.agents.sizing_agent import SizingAgent
    from aeroloop.schemas.requirement import RequirementReasoningResult
    from aeroloop.schemas.engineering import SizingRequest, SizingConfig
    from aeroloop.schemas.aircraft import AircraftCandidate
    from aeroloop.schemas.mission import MissionProfile
    
    agent = SizingAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading reasoning results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = RequirementReasoningResult(**data)
        
        # Load mission profile
        mission_file = input_file.parent / f"mission_parsing_result.json"
        if not mission_file.exists():
            mission_file = input_file.parent / f"mission_parsing_result_{req_result.run_id}.json"
            
        if mission_file.exists():
            with open(mission_file, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                mission_profile = MissionProfile(**m_data.get("mission_profile", {}))
        else:
            mission_profile = MissionProfile()
            
        candidate_id = f"AC-{req_result.run_id[-6:]}"
        candidate = AircraftCandidate(
            candidate_id=candidate_id,
            aircraft_type="lift_cruise_vtol",
            passenger_capacity=mission_profile.passenger_count if hasattr(mission_profile, 'passenger_count') and mission_profile.passenger_count else 4
        )
        
        sizing_req = SizingRequest(
            sizing_request_id=f"REQ-SIZ-{req_result.run_id[-6:]}",
            run_id=req_result.run_id,
            mission_id=req_result.run_id,
            candidate_id=candidate_id,
            mission_profile=mission_profile,
            aircraft_candidate=candidate,
            sizing_config=SizingConfig(),
            final_requirements=req_result.final_requirements
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running SizingAgent ---")
    try:
        result = agent.size(sizing_req)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"sizing_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Sizing completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        if result.sizing_result:
            print(f"MTOW (kg)                  : {result.sizing_result.mtow_kg:.1f}")
        if result.geometry_parameter_set:
            print(f"Wing Area (m2)             : {result.geometry_parameter_set.wing_area_m2}")
            print(f"Total Disk Area (m2)       : {result.geometry_parameter_set.total_disk_area_m2}")
            
    except Exception as e:
        print(f"\n[ERROR] SizingAgent failed: {e}")
        raise

def run_geometry_agent(args):
    """Run the GeometryDesignAgent on a previously generated SizingAgentResult."""
    print("Initializing GeometryDesignAgent...")
    import sys
    sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
    from aeroloop.agents.geometry_design_agent import GeometryDesignAgent
    from aeroloop.schemas.engineering import SizingAgentResult
    from aeroloop.schemas.geometry import GeometryDesignRequest, GeometryValidationOptions
    
    agent = GeometryDesignAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading sizing results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        sizing_res = SizingAgentResult(**data)
        
        geo_params = sizing_res.geometry_parameter_set
        
        out_dir = config.get_run_dir(sizing_res.run_id) / "geometry_artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        req = GeometryDesignRequest(
            geometry_request_id=f"REQ-GEO-{sizing_res.run_id[-6:]}",
            run_id=sizing_res.run_id,
            mission_id=sizing_res.mission_id,
            candidate_id=sizing_res.candidate_id,
            vehicle_type=geo_params.aircraft_type if geo_params else "lift_cruise_vtol",
            geometry_template="lift_cruise_vtol_template_v1",
            design_parameters=geo_params.model_dump(exclude_none=True) if geo_params else {},
            output_directory=str(out_dir),
            validation_options=GeometryValidationOptions(validate_mesh=True)
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running GeometryDesignAgent ---")
    try:
        result = agent.process_request(req)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"geometry_design_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Geometry Design completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")
        
        artifacts = result.geometry_artifacts
        print(f"\n--- Summary ---")
        if artifacts:
            print(f"VSP3 File                 : {artifacts.vsp3_file_path}")
            print(f"STL File                  : {artifacts.stl_file_path}")
        print(f"Warnings                  : {len(result.warnings)}")
        print(f"Errors                    : {len(result.errors)}")
            
    except Exception as e:
        print(f"\n[ERROR] GeometryDesignAgent failed: {e}")
        raise

def run_aerodynamics_agent(args):
    """Run the AerodynamicsAnalysisAgent on a previously generated GeometryDesignResult."""
    print("Initializing AerodynamicsAnalysisAgent...")
    import sys
    sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
    from aeroloop.agents.aerodynamics_analysis_agent import AerodynamicsAnalysisAgent
    from aeroloop.schemas.geometry import GeometryDesignResult
    from aeroloop.schemas.aerodynamics import AerodynamicsAnalysisRequest, AeroAnalysisConfig, AircraftCandidate, GeometryArtifacts
    
    agent = AerodynamicsAnalysisAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading geometry results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        geo_result = GeometryDesignResult(**data)
        
        out_dir = config.get_run_dir(geo_result.run_id) / "aerodynamics_output"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        req = AerodynamicsAnalysisRequest(
            aero_analysis_request_id=f"AERO-REQ-{geo_result.run_id[-6:]}",
            run_id=geo_result.run_id,
            mission_id=geo_result.mission_id if hasattr(geo_result, "mission_id") else "unknown_mission",
            candidate_id=geo_result.candidate_id,
            geometry_result_id=geo_result.geometry_result_id if hasattr(geo_result, "geometry_result_id") else "GEO-RES-001",
            aircraft_candidate=AircraftCandidate(
                candidate_id=geo_result.candidate_id,
                aircraft_type="unknown",
                template_id="TPL-001"
            ),
            geometry_artifacts=GeometryArtifacts(
                vsp3_file_path=geo_result.geometry_artifacts.vsp3_file_path
            ),
            analysis_config=AeroAnalysisConfig(
                analysis_backend="openvsp_vspaero",
                analysis_fidelity="low",
                run_mass_properties=True,
                run_vspaero=False
            ),
            output_directory=str(out_dir)
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs from {input_file.name}: {e}")
        return

    print("\n--- Running AerodynamicsAnalysisAgent ---")
    try:
        res = agent.run({"analysis_request": req})
        result = res.get("analysis_result")
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"aerodynamics_analysis_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Aerodynamics Analysis completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")
        
        print("\n  [Aerodynamics Analysis Summary]")
        print(f"  Status: {result.status.upper()}")
        if result.aerodynamic_summary:
            summary = result.aerodynamic_summary
            if summary.cl_alpha_per_deg is not None:
                print(f"  Lift Curve Slope (dCl/dAlpha): {summary.cl_alpha_per_deg:.4f} /deg")
            if summary.cd_min is not None:
                print(f"  Minimum Drag (Cd0)           : {summary.cd_min:.4f}")
            if summary.max_lift_to_drag is not None:
                print(f"  Max L/D                      : {summary.max_lift_to_drag:.2f}")
        if result.mass_properties:
            mp = result.mass_properties
            if mp.mass_analysis_available:
                print(f"  Estimated Total Mass         : {mp.total_mass_kg:.1f} kg")
                if mp.center_of_gravity_m:
                    cg = mp.center_of_gravity_m
                    print(f"  Center of Gravity (x,y,z)    : ({cg[0]:.2f}, {cg[1]:.2f}, {cg[2]:.2f}) m")
        if result.aerodynamic_coefficients:
            for case in result.aerodynamic_coefficients[:1]:
                if case.load_distribution and len(case.load_distribution) > 0:
                    ld = case.load_distribution[0]
                    print(f"  Spanwise Load Data           : Extracted {len(ld.y_span)} sections (e.g. Max Cl: {max(ld.cl):.3f})")
                    break
        if result.analysis_artifacts and result.analysis_artifacts.load_distribution_csv_path:
            print(f"  Load Distribution File       : {result.analysis_artifacts.load_distribution_csv_path}")
        if result.warnings:
            print(f"  Warnings: {len(result.warnings)}")
            for w in result.warnings[:3]:
                print(f"    - {w}")
            if len(result.warnings) > 3:
                print(f"    - ... and {len(result.warnings) - 3} more")
        if result.errors:
            print(f"  Errors: {len(result.errors)}")
            for e in result.errors[:3]:
                print(f"    - {e.message}")
            
    except Exception as e:
        print(f"\n[ERROR] AerodynamicsAnalysisAgent failed: {e}")
        raise

def run_validator_agent(args):
    """Run the CertificationValidatorAgent on a reasoning result and compliance result."""
    print("Initializing CertificationValidatorAgent...")
    from aeroloop.agents.certification_validator_agent import CertificationValidatorAgent
    from aeroloop.schemas.compliance import CertificationValidationInput, CertificationComplianceResult
    from aeroloop.schemas.requirement import RequirementReasoningResult
    
    agent = CertificationValidatorAgent()
    
    input_file = Path(args.input_file)
    if not input_file.exists():
        print(f"\n[ERROR] File not found: {input_file.absolute()}")
        return

    print(f"Loading reasoning results from: {input_file.absolute()}")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        req_result = RequirementReasoningResult(**data)
        
        # Load compliance result
        comp_file = input_file.parent / f"certification_compliance_result.json"
        if not comp_file.exists():
            comp_file = input_file.parent / f"certification_compliance_result_{req_result.run_id}.json"
            
        if not comp_file.exists():
            print(f"\n[ERROR] Certification compliance result not found: {comp_file.absolute()}")
            return
            
        with open(comp_file, "r", encoding="utf-8") as cf:
            c_data = json.load(cf)
            comp_result = CertificationComplianceResult(**c_data)
            
        if not req_result.concept_baseline:
            print("\n[ERROR] ConceptBaseline is missing from RequirementReasoningResult.")
            return
            
        val_input = CertificationValidationInput(
            run_id=req_result.run_id,
            concept_baseline=req_result.concept_baseline,
            compliance_result=comp_result
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to load inputs: {e}")
        return

    print("\n--- Running CertificationValidatorAgent ---")
    try:
        result = agent.validate(val_input)
        
        run_dir = config.get_run_dir(result.run_id)
        output_file = run_dir / f"certification_validation_result.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        print(f"\n[SUCCESS] Validation completed. Status: {result.status}")
        print(f"JSON Data saved to: {output_file.absolute()}")

        print("\n--- Summary ---")
        print(f"Is Valid                   : {result.is_valid}")
        print(f"Violations                 : {len(result.violations)}")
        for v in result.violations:
            print(f"  - [VIOLATION] {v}")
        print(f"Warnings                   : {len(result.warnings)}")
        for w in result.warnings:
            print(f"  - [WARNING] {w}")
            
    except Exception as e:
        print(f"\n[ERROR] CertificationValidatorAgent failed: {e}")
        raise

def run_workflow(args):
    """Run the entire bidirectional LangGraph workflow."""
    from aeroloop.orchestration.workflow import create_workflow
    from aeroloop.schemas.mission import MissionParsingInput
    import uuid
    
    print("Initializing LangGraph Workflow...")
    app = create_workflow()
    
    raw_text = load_mission_text(args.text)
    
    initial_state = {
        "run_id": f"RUN-{uuid.uuid4().hex[:8]}",
        "raw_input": MissionParsingInput(
            mission_id=f"mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            raw_user_input=raw_text
        ),
        "mission_profile": None,
        "status": "running",
        "full_auto": getattr(args, "full_auto", False)
    }
    
    print("\n--- Starting Bidirectional Workflow ---")
    try:
        from aeroloop.config import config
        from langgraph.types import Command
        
        graph_config = {
            "configurable": {"thread_id": "cli_run_1"},
            "recursion_limit": config.max_workflow_iterations
        }
        
        stream_input = initial_state
        
        while True:
            for s in app.stream(stream_input, config=graph_config):
                node_name = list(s.keys())[0]
                print(f"\n[Node Execution: {node_name}]")
                state_update = s[node_name]
                
                if "status" in state_update:
                    print(f"  Status: {state_update['status']}")
                if "next_node" in state_update:
                    print(f"  Routing -> {state_update['next_node']}")
                if "feedback_history" in state_update and state_update["feedback_history"]:
                    label = "Reason" if node_name == "orchestrator" else "Feedback"
                    print(f"  {label}: {state_update['feedback_history'][-1]}")
                
                # Print intermediate results for visibility
                if "candidate_requirements" in state_update and state_update["candidate_requirements"]:
                    print(f"  Generated {len(state_update['candidate_requirements'])} candidate requirements.")
                
                if "analysis_result" in state_update and state_update["analysis_result"]:
                    res = state_update["analysis_result"]
                    print("\n  [Aerodynamics Analysis Summary]")
                    print(f"  Status: {res.status.upper()}")
                    if res.aerodynamic_summary:
                        summary = res.aerodynamic_summary
                        if summary.cl_alpha_per_deg is not None:
                            print(f"  Lift Curve Slope (dCl/dAlpha): {summary.cl_alpha_per_deg:.4f} /deg")
                        if summary.cd_min is not None:
                            print(f"  Minimum Drag (Cd0)           : {summary.cd_min:.4f}")
                        if summary.max_lift_to_drag is not None:
                            print(f"  Max L/D                      : {summary.max_lift_to_drag:.2f}")
                    if res.mass_properties:
                        mp = res.mass_properties
                        if mp.mass_analysis_available:
                            print(f"  Estimated Total Mass         : {mp.total_mass_kg:.1f} kg")
                            if mp.center_of_gravity_m:
                                cg = mp.center_of_gravity_m
                                print(f"  Center of Gravity (x,y,z)    : ({cg[0]:.2f}, {cg[1]:.2f}, {cg[2]:.2f}) m")
                    if res.aerodynamic_coefficients:
                        for case in res.aerodynamic_coefficients[:1]:
                            if case.load_distribution and len(case.load_distribution) > 0:
                                ld = case.load_distribution[0]
                                print(f"  Spanwise Load Data           : Extracted {len(ld.y_span)} sections (e.g. Max Cl: {max(ld.cl):.3f})")
                                break
                    if res.analysis_artifacts and res.analysis_artifacts.load_distribution_csv_path:
                        print(f"  Load Distribution File       : {res.analysis_artifacts.load_distribution_csv_path}")
                    if res.warnings:
                        print(f"  Warnings: {len(res.warnings)}")
                        for w in res.warnings[:3]:
                            print(f"    - {w}")
                        if len(res.warnings) > 3:
                            print(f"    - ... and {len(res.warnings) - 3} more")
                    if res.errors:
                        print(f"  Errors: {len(res.errors)}")
                        for e in res.errors[:3]:
                            print(f"    - {e.message}")
            
            # Check if graph is paused due to interrupt
            state_snapshot = app.get_state(graph_config)
            if state_snapshot.tasks and state_snapshot.tasks[0].interrupts:
                interrupt_payload = state_snapshot.tasks[0].interrupts[0].value
                print(f"\n--- [HITL Required: {interrupt_payload.get('awaiting_from')}] ---")
                
                if interrupt_payload.get("missing_fields"):
                    print("Missing Information:")
                    for mf in interrupt_payload.get("missing_fields", []):
                        print(f"  - {mf.get('field_name')}: {mf.get('suggested_question')}")
                        
                if interrupt_payload.get("unresolved_questions"):
                    print("Unresolved Questions:")
                    for q in interrupt_payload.get("unresolved_questions", []):
                        print(f"  - {q}")
                        
                user_reply = input("\n[User] Provide input (or type 'skip'/'auto' to let AI infer): ")
                stream_input = Command(resume=user_reply)
            else:
                break
        
        state_snapshot = app.get_state(graph_config)
        final_status = state_snapshot.values.get("status", "unknown") if hasattr(state_snapshot, "values") else "unknown"
        if final_status == "failed":
            print("\n[FAILED] Workflow execution completed with errors.")
        else:
            print("\n[SUCCESS] Workflow execution completed.")
    except Exception as e:
        print(f"\n[ERROR] Workflow failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="AeroLoop High-Level Agent Execution CLI")
    subparsers = parser.add_subparsers(dest="agent", help="Which agent to run")
    subparsers.required = True

    # MissionParsingAgent subparser
    mission_parser = subparsers.add_parser("mission", help="Run the MissionParsingAgent")
    
    # GUI subparser
    gui_parser = subparsers.add_parser("gui", help="Launch the AeroLoop Gradio Dashboard")
    mission_parser.add_argument(
        "text",
        type=str,
        help=(
            "The natural language mission description to parse. "
            "Pass 'demo' to load from demo_requirements.md."
        )
    )

    # CustomerRequirementAgent subparser
    customer_parser = subparsers.add_parser("customer", help="Run the CustomerRequirementAgent")
    customer_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the parsed MissionProfile (e.g. results/default_user/RUN-XXX/mission_parsing_result.json)"
    )

    # CertificationComplianceAgent subparser
    certification_parser = subparsers.add_parser("certification", help="Run the CertificationComplianceAgent")
    certification_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the CustomerRequirementResult (e.g. results/default_user/RUN-XXX/customer_requirements_result.json)"
    )

    # RequirementReasoningAgent subparser
    reasoning_parser = subparsers.add_parser("reasoning", help="Run the RequirementReasoningAgent")
    reasoning_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the CustomerRequirementResult (e.g. results/default_user/RUN-XXX/customer_requirements_result.json)"
    )

    # SizingAgent subparser
    sizing_parser = subparsers.add_parser("sizing", help="Run the SizingAgent")
    sizing_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the RequirementReasoningResult (e.g. results/default_user/RUN-XXX/requirement_reasoning_result.json)"
    )

    # ValidatorAgent subparser
    validator_parser = subparsers.add_parser("validator", help="Run the CertificationValidatorAgent")
    validator_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the RequirementReasoningResult (e.g. results/default_user/RUN-XXX/requirement_reasoning_result.json)"
    )

    # GeometryDesignAgent subparser
    geometry_parser = subparsers.add_parser("geometry", help="Run the GeometryDesignAgent")
    geometry_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the SizingAgentResult (e.g. results/default_user/RUN-XXX/sizing_result.json)"
    )

    # AerodynamicsAnalysisAgent subparser
    aerodynamics_parser = subparsers.add_parser("aerodynamics", help="Run the AerodynamicsAnalysisAgent")
    aerodynamics_parser.add_argument(
        "input_file",
        type=str,
        help="Path to the JSON file containing the GeometryDesignResult (e.g. results/default_user/RUN-XXX/geometry_design_result.json)"
    )

    # Workflow subparser
    workflow_parser = subparsers.add_parser("workflow", help="Run the Bidirectional LangGraph Workflow")
    workflow_parser.add_argument(
        "text",
        type=str,
        help="The natural language mission description. Pass 'demo' to load from demo_requirements.md."
    )
    workflow_parser.add_argument(
        "--full-auto",
        action="store_true",
        help="Run the entire workflow automatically without any human-in-the-loop prompts."
    )

    args = parser.parse_args()

    # Ensure the fallback .agents directory exists
    ensure_agents_dir()

    if args.agent == "gui":
        from aeroloop.gui.app import build_app
        app = build_app()
        app.launch(share=False)
    elif args.agent == "mission":
        run_mission_agent(args)
    elif args.agent == "customer":
        run_customer_agent(args)
    elif args.agent == "certification":
        run_certification_agent(args)
    elif args.agent == "reasoning":
        run_reasoning_agent(args)
    elif args.agent == "sizing":
        run_sizing_agent(args)
    elif args.agent == "geometry":
        run_geometry_agent(args)
    elif args.agent == "aerodynamics":
        run_aerodynamics_agent(args)
    elif args.agent == "validator":
        run_validator_agent(args)
    elif args.agent == "workflow":
        run_workflow(args)
    else:
        print(f"Unknown agent: {args.agent}")

if __name__ == "__main__":
    main()

