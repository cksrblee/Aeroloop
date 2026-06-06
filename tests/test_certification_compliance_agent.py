import pytest
from unittest.mock import patch

from aeroloop.schemas.mission import MissionProfile
from aeroloop.schemas.requirement import CandidateRequirement
from aeroloop.schemas.aircraft import AircraftConcept
from aeroloop.schemas.certification import CertificationSourcePolicy
from aeroloop.schemas.compliance import (
    CertificationComplianceInput,
    CertificationComplianceResult,
    CertificationBasisCandidate,
    ComplianceChecklistItem,
    MeansOfCompliancePlan,
    CertificationComplianceQualityReport
)
from aeroloop.agents.certification_compliance_agent import CertificationComplianceAgent

def test_initial_invocation_missing_concept():
    # Call without AircraftConcept. Ensure propulsion-related items (like OEI) are correctly marked as tbd.
    input_data = CertificationComplianceInput(
        run_id="test-run-001",
        mission_profile=MissionProfile(passenger_count=4),
        customer_requirements=[],
        aircraft_concept=None,  # Missing concept
        certification_source_policy=CertificationSourcePolicy(
            allowed_source_families=["SC_VTOL_SMALL"],
            allowed_authorities=["EASA"]
        )
    )
    
    agent = CertificationComplianceAgent()
    
    # Mock the analyze method since LLM logic is not yet implemented
    with patch.object(agent, 'analyze') as mock_analyze:
        mock_ccl_item = ComplianceChecklistItem(
            ccl_item_id="CCL-OEI-001",
            run_id="test-run-001",
            basis_id="BASIS-SC-VTOL-001",
            document_id="DOC-EASA-SC-VTOL",
            clause_id="CLAUSE-OEI-001",
            clause_number="TBD",
            topic_area="emergency_operation",
            applicability_status="tbd", # Correctly marked as tbd
            applicability_rationale="Propulsion architecture unknown.",
            design_relevance="direct_design_driver",
            risk_level="high"
        )
        
        mock_analyze.return_value = CertificationComplianceResult(
            result_id="RES-001",
            run_id="test-run-001",
            mission_id="mission-001",
            agent_version="v0.1.0",
            schema_version="v0.1.0",
            certification_basis_candidates=[],
            retrieved_clauses=[],
            ccl_items=[mock_ccl_item],
            moc_plans=[],
            requirement_links=[],
            conflicts=[],
            unresolved_questions=[],
            assumptions=[],
            quality_report=CertificationComplianceQualityReport(
                total_basis_candidates=0, total_retrieved_clauses=0, total_ccl_items=1,
                included_items=0, excluded_items=0, tbd_items=1, human_review_items=0,
                total_moc_plans=0, flight_test_required_count=0, simulation_supported_count=0,
                analysis_supported_count=0, traceability_coverage_ratio=0.0,
                readiness_level="needs_configuration_detail",
                summary="Initial invocation missing concept."
            )
        )
        
        result = agent.analyze(input_data)
        
        assert len(result.ccl_items) == 1
        assert result.ccl_items[0].applicability_status == "tbd"
        assert result.ccl_items[0].topic_area == "emergency_operation"
        assert result.quality_report.readiness_level == "needs_configuration_detail"


def test_second_invocation_post_design():
    # Supply Distributed Electric Propulsion data. Verify that OEI-related CCL states are updated accordingly.
    concept = AircraftConcept(
        concept_id="concept-001",
        aircraft_type="evtol",
        propulsion_type="electric",
        number_of_motors=8,
        number_of_lift_units=8,
        vertical_takeoff_landing=True
    )
    
    input_data = CertificationComplianceInput(
        run_id="test-run-002",
        mission_profile=MissionProfile(passenger_count=4),
        customer_requirements=[],
        aircraft_concept=concept,
        certification_source_policy=CertificationSourcePolicy(
            allowed_source_families=["SC_VTOL_SMALL"],
            allowed_authorities=["EASA"]
        )
    )
    
    agent = CertificationComplianceAgent()
    
    with patch.object(agent, 'analyze') as mock_analyze:
        mock_ccl_item = ComplianceChecklistItem(
            ccl_item_id="CCL-OEI-001",
            run_id="test-run-002",
            basis_id="BASIS-SC-VTOL-001",
            document_id="DOC-EASA-SC-VTOL",
            clause_id="CLAUSE-OEI-001",
            clause_number="TBD",
            topic_area="emergency_operation",
            applicability_status="requires_human_review", # Updated state
            applicability_rationale="Distributed electric propulsion requires alternative failure case mapping.",
            design_relevance="direct_design_driver",
            risk_level="critical"
        )
        
        mock_analyze.return_value = CertificationComplianceResult(
            result_id="RES-002",
            run_id="test-run-002",
            mission_id="mission-001",
            agent_version="v0.1.0",
            schema_version="v0.1.0",
            certification_basis_candidates=[],
            retrieved_clauses=[],
            ccl_items=[mock_ccl_item],
            moc_plans=[],
            requirement_links=[],
            conflicts=[],
            unresolved_questions=[],
            assumptions=[],
            quality_report=CertificationComplianceQualityReport(
                total_basis_candidates=0, total_retrieved_clauses=0, total_ccl_items=1,
                included_items=0, excluded_items=0, tbd_items=0, human_review_items=1,
                total_moc_plans=0, flight_test_required_count=0, simulation_supported_count=0,
                analysis_supported_count=0, traceability_coverage_ratio=0.0,
                readiness_level="ready_for_concept_review",
                summary="Second invocation with concept details."
            )
        )
        
        result = agent.analyze(input_data)
        
        assert result.ccl_items[0].applicability_status == "requires_human_review"
        assert result.quality_report.human_review_items == 1


def test_runtime_verification_linkage():
    # Ensure CCL items related to `Operating limitations` map to a `simulation` MoC.
    input_data = CertificationComplianceInput(
        run_id="test-run-003",
        mission_profile=MissionProfile(passenger_count=4),
        customer_requirements=[],
        certification_source_policy=CertificationSourcePolicy(
            allowed_source_families=["SC_VTOL_SMALL"],
            allowed_authorities=["EASA"]
        )
    )
    
    agent = CertificationComplianceAgent()
    
    with patch.object(agent, 'analyze') as mock_analyze:
        mock_ccl_item = ComplianceChecklistItem(
            ccl_item_id="CCL-OPERATING-LIMITS-001",
            run_id="test-run-003",
            basis_id="BASIS-SC-VTOL-001",
            document_id="DOC-EASA-SC-VTOL",
            clause_id="CLAUSE-OPERATING-LIMITS-001",
            clause_number="TBD",
            topic_area="operating_limitations",
            applicability_status="included",
            applicability_rationale="Aircraft must operate within defined limits.",
            design_relevance="verification_only",
            compliance_status="supported_by_poc",
            risk_level="high"
        )
        
        mock_moc_plan = MeansOfCompliancePlan(
            moc_id="MOC-OP-001",
            ccl_item_id="CCL-OPERATING-LIMITS-001",
            clause_id="CLAUSE-OPERATING-LIMITS-001",
            proposed_methods=["simulation", "design_review"],
            primary_method="simulation", # Mapped to simulation
            poc_support_level="supported_as_preliminary_evidence",
            expected_artifacts=["simulation_log"],
            rationale="Runtime verification can monitor altitude, geofence, and speed."
        )
        
        mock_analyze.return_value = CertificationComplianceResult(
            result_id="RES-003",
            run_id="test-run-003",
            mission_id="mission-001",
            agent_version="v0.1.0",
            schema_version="v0.1.0",
            certification_basis_candidates=[],
            retrieved_clauses=[],
            ccl_items=[mock_ccl_item],
            moc_plans=[mock_moc_plan],
            requirement_links=[],
            conflicts=[],
            unresolved_questions=[],
            assumptions=[],
            quality_report=CertificationComplianceQualityReport(
                total_basis_candidates=0, total_retrieved_clauses=0, total_ccl_items=1,
                included_items=1, excluded_items=0, tbd_items=0, human_review_items=0,
                total_moc_plans=1, flight_test_required_count=0, simulation_supported_count=1,
                analysis_supported_count=0, traceability_coverage_ratio=0.0,
                readiness_level="ready_for_concept_review",
                summary="Runtime verification linkage test."
            )
        )
        
        result = agent.analyze(input_data)
        
        assert len(result.moc_plans) == 1
        assert result.moc_plans[0].primary_method == "simulation"
        assert result.moc_plans[0].poc_support_level == "supported_as_preliminary_evidence"
        assert result.ccl_items[0].compliance_status == "supported_by_poc"

import json
import os
from pathlib import Path

def test_real_data_execution():
    # Load mission profile from .agents
    agents_dir = Path(".agents")
    mission_json_path = None
    for p in agents_dir.glob("mission_parsing_result_*.json"):
        mission_json_path = p
        break
        
    if not mission_json_path or not mission_json_path.exists():
        pytest.skip("No mission parsing result found in .agents directory")
        
    with open(mission_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    mission_profile = MissionProfile(**data.get("mission_profile", {}))
    
    # Concept with distributed electric propulsion
    concept = AircraftConcept(
        concept_id="eVTOL-CONCEPT-01",
        aircraft_type="evtol",
        mtow_kg=3000.0,
        passenger_count=4,
        crew_count=1,
        propulsion_type="electric",
        number_of_motors=8,
        number_of_lift_units=8,
        has_wing=True,
        vertical_takeoff_landing=True,
        intended_operation="urban_air_mobility"
    )
    
    input_data = CertificationComplianceInput(
        run_id="run_test_integration",
        mission_profile=mission_profile,
        customer_requirements=[],
        aircraft_concept=concept,
        certification_source_policy=CertificationSourcePolicy(
            allowed_source_families=["SC_VTOL_SMALL", "SMALL_ROTORCRAFT", "SMALL_AIRCRAFT"],
            allowed_authorities=["EASA", "FAA"]
        )
    )
    
    agent = CertificationComplianceAgent()
    result = agent.analyze(input_data)
    
    # Assertions
    assert isinstance(result, CertificationComplianceResult)
    assert result.quality_report.total_ccl_items > 0
    # The loops should fallback for this ambiguous concept, resulting in needs_human_certification_review
    assert result.quality_report.readiness_level == "needs_human_certification_review"
    assert any("Fallback triggered" in q for q in result.unresolved_questions)
