from typing import Literal, Optional, List
from pydantic import BaseModel

class MeansOfCompliancePlan(BaseModel):
    moc_id: str
    ccl_item_id: str
    clause_id: str

    proposed_methods: List[Literal[
        "design_review",
        "drawing_inspection",
        "engineering_analysis",
        "simulation",
        "ground_test",
        "flight_test",
        "software_verification",
        "safety_assessment",
        "similarity",
        "expert_review"
    ]]

    primary_method: Literal[
        "design_review",
        "drawing_inspection",
        "engineering_analysis",
        "simulation",
        "ground_test",
        "flight_test",
        "software_verification",
        "safety_assessment",
        "similarity",
        "expert_review"
    ]

    poc_support_level: Literal[
        "not_supported",
        "partially_supported",
        "supported_as_preliminary_evidence",
        "requires_real_test"
    ]

    expected_artifacts: List[Literal[
        "drawing",
        "analysis_report",
        "simulation_log",
        "flight_test_report",
        "ground_test_report",
        "safety_assessment_report",
        "software_verification_report",
        "inspection_record",
        "traceability_matrix"
    ]]

    rationale: str
    limitations: List[str] = []
