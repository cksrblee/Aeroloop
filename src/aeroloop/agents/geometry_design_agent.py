import os
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

try:
    from langfuse.decorators import observe
except ImportError:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.geometry import (
    GeometryDesignRequest,
    GeometryDesignResult,
    GeometryArtifacts,
    GeometryComponent,
    MeshValidationReport,
    TraceLink,
    ComplianceArtifactLink,
    ErrorInfo
)
from aeroloop.utils.ids import make_id

class GeometryDesignAgent(BaseAIAgent):
    """
    GeometryDesignAgent translates design requirements and sizing parameters into a traceable
    parametric 3D geometry model using OpenVSP. It acts as a Requirement-to-Geometry Compiler.
    """
    def __init__(self, agent_version: str = "v0.2.0", **kwargs):
        super().__init__(
            name="Geometry Design Agent",
            description="Compiles design requirements into parametric OpenVSP geometry and generates simulation artifacts.",
            **kwargs
        )
        self.agent_version = agent_version

    def _generate_id(self, prefix: str, base_id: str, salt: str = "") -> str:
        """Generates a deterministic ID based on a base_id and salt."""
        hash_str = hashlib.md5(f"{base_id}-{salt}".encode()).hexdigest()[:8]
        return f"{prefix}-{hash_str}"

    @observe()
    def process_request(self, request: GeometryDesignRequest) -> GeometryDesignResult:
        log_messages = []
        warnings = []
        errors = []
        status = "success"

        # 1. Isolate output directory
        out_dir = request.output_directory
        os.makedirs(out_dir, exist_ok=True)
        log_messages.append(f"Initialized run directory at {out_dir}")

        # Check OpenVSP
        try:
            import sys
            openvsp_path = os.environ.get("OPENVSP_PYTHON_PATH", "/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp")
            if openvsp_path not in sys.path:
                sys.path.insert(0, openvsp_path)
            import openvsp as vsp
        except ImportError:
            return self._fail(request, "VSP_MODULE_MISSING", "OpenVSP Python API is not installed or available.", recoverable=False)

        # 2. Validate input parameters & apply template defaults
        try:
            params, gen_warnings, gen_errors = self._validate_and_apply_defaults(request)
            warnings.extend(gen_warnings)
            if gen_errors:
                errors.extend(gen_errors)
                return self._build_result(request, "failed", GeometryArtifacts(), [], None, [], [], warnings, errors, "Validation failed")
        except Exception as e:
            return self._fail(request, "VALIDATION_ERROR", str(e), recoverable=False)

        # 3. Generate Geometry Components via OpenVSP Template
        generated_components = []
        artifacts = GeometryArtifacts()
        
        try:
            vsp.VSPRenew()
            vsp.Update()
            log_messages.append("Cleared previous OpenVSP workspace.")
            
            from aeroloop.design.openvsp_template_executor import (
                load_openvsp_template,
                build_openvsp_from_template,
                export_from_template,
            )

            template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "design", "openvsp_maximal_geometry_template.yaml")
            template = load_openvsp_template(template_path)

            report = build_openvsp_from_template(
                vsp=vsp,
                template=template,
                design_parameters=params,
            )

            if report.errors:
                return self._fail(
                    request,
                    "VSP_TEMPLATE_BUILD_ERROR",
                    "; ".join(report.errors),
                    recoverable=False,
                )
                
            for w in report.warnings:
                warnings.append(f"Template Warning: {w}")

            # Populate generated_components dynamically from the template report
            for comp_name, geom_id in report.geom_ids.items():
                comp_params = {}
                for p in report.applied_parms:
                    # Match any parameter applied within this component's context
                    if p.get("context", "").startswith(comp_name):
                        comp_params[p["name"]] = p["value"]
                
                generated_components.append(GeometryComponent(
                    component_id=str(geom_id),
                    component_type="OpenVSP_Geom",
                    name=comp_name,
                    parameters=comp_params
                ))

            exported = export_from_template(
                vsp=vsp,
                template=template,
                output_dir=out_dir,
                candidate_id=request.candidate_id,
                report=report,
            )

            artifacts.vsp3_file_path = exported.get("vsp3")
            artifacts.stl_file_path = exported.get("stl")
            artifacts.geometry_manifest_path = exported.get("template_manifest")
            
            log_messages.append("Exported geometry from template and populated dynamic components.")
                
        except Exception as e:
            return self._fail(request, "VSP_EXECUTION_ERROR", f"OpenVSP failed: {str(e)}", recoverable=False)

        # 5. Validate Mesh using Open3D
        mesh_validation = None
        if request.validation_options.validate_mesh and artifacts.stl_file_path:
            mesh_validation, mesh_warnings, mesh_errors = self._validate_mesh(artifacts.stl_file_path, request.validation_options)
            warnings.extend(mesh_warnings)
            errors.extend(mesh_errors)
            if mesh_errors:
                status = "failed"
            elif mesh_warnings:
                status = "success_with_warnings"

        # 6. Generate Manifest & Traceability Links
        trace_links = []
        for src in request.parameter_sources:
            trace_links.append(TraceLink(
                source_type=src.source_type,
                source_id=src.source_id,
                target_type="GeometryArtifact",
                target_id=artifacts.vsp3_file_path or "unknown",
                relation_type="generated_from"
            ))

        compliance_links = []
        if request.compliance_context and request.compliance_context.ccl_item_ids:
            # We associate generated artifacts with the given CCLs
            art_ids = [p for p in [artifacts.vsp3_file_path, artifacts.stl_file_path] if p]
            for ccl_id in request.compliance_context.ccl_item_ids:
                compliance_links.append(ComplianceArtifactLink(
                    ccl_item_id=ccl_id,
                    moc_type="analysis",
                    artifact_ids=art_ids,
                    evidence_role="candidate_design_evidence"
                ))

        # Save manifest
        manifest_path = os.path.join(out_dir, "geometry_manifest.json")
        artifacts.geometry_manifest_path = manifest_path
        
        manifest_data = {
            "geometry_request_id": request.geometry_request_id,
            "generated_components": [c.dict() for c in generated_components],
            "trace_links": [t.dict() for t in trace_links]
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

        return self._build_result(
            request, status, artifacts, generated_components, mesh_validation, 
            trace_links, compliance_links, warnings, errors, "\\n".join(log_messages)
        )

    def _validate_and_apply_defaults(self, request: GeometryDesignRequest) -> Tuple[Dict[str, Any], List[str], List[ErrorInfo]]:
        params = request.design_parameters.copy()
        warnings = []
        errors = []

        for k, v in params.items():
            if isinstance(v, (int, float)) and v < 0:
                if not k.endswith("_deg") and "x" not in k and "y" not in k and "z" not in k:
                    errors.append(ErrorInfo(error_code="INVALID_DIMENSION", message=f"{k} must be >= 0.", field=f"design_parameters.{k}"))
        
        return params, warnings, errors

    def _validate_mesh(self, stl_path: str, options: Any) -> Tuple[MeshValidationReport, List[str], List[ErrorInfo]]:
        warnings = []
        errors = []
        try:
            import open3d as o3d
        except ImportError:
            warnings.append("Open3D is not installed. Skipping mesh validation.")
            return MeshValidationReport(stl_exists=os.path.exists(stl_path), loadable_by_open3d=False, validation_status="passed_with_warnings", warnings=["Open3D missing"]), warnings, errors

        if not os.path.exists(stl_path):
            errors.append(ErrorInfo(error_code="MESH_MISSING", message="STL file not found.", field="stl_file_path"))
            return None, warnings, errors

        file_size = os.path.getsize(stl_path)
        if file_size == 0:
            errors.append(ErrorInfo(error_code="MESH_EMPTY", message="STL file is empty.", field="stl_file_path"))
            return None, warnings, errors

        mesh = o3d.io.read_triangle_mesh(stl_path)
        if mesh.is_empty():
            errors.append(ErrorInfo(error_code="MESH_LOAD_FAILED", message="Open3D could not load the mesh.", field="stl_file_path"))
            return None, warnings, errors
        
        is_watertight = mesh.is_watertight()
        if not is_watertight:
            warnings.append("Mesh is not watertight; acceptable for visualization but not for CFD-grade analysis.")
            if options.strict_watertight:
                errors.append(ErrorInfo(error_code="MESH_NOT_WATERTIGHT", message="Strict watertight check failed."))

        bbox = mesh.get_axis_aligned_bounding_box()
        extent = bbox.get_extent()

        report = MeshValidationReport(
            stl_exists=True,
            loadable_by_open3d=True,
            file_size_bytes=file_size,
            vertex_count=len(mesh.vertices),
            triangle_count=len(mesh.triangles),
            is_watertight=is_watertight,
            bbox_dimensions_m={"x": float(extent[0]), "y": float(extent[1]), "z": float(extent[2])},
            validation_status="passed" if not errors and not warnings else ("failed" if errors else "passed_with_warnings"),
            warnings=warnings,
            errors=[e.message for e in errors]
        )
        return report, warnings, errors

    def _fail(self, request: GeometryDesignRequest, code: str, msg: str, recoverable: bool = False) -> GeometryDesignResult:
        err = ErrorInfo(error_code=code, message=msg, recoverable=recoverable)
        return self._build_result(request, "failed", GeometryArtifacts(), [], None, [], [], [], [err], msg)

    def _build_result(self, request: GeometryDesignRequest, status: str, artifacts: GeometryArtifacts, 
                      components: List[GeometryComponent], validation: MeshValidationReport,
                      trace_links: List[TraceLink], comp_links: List[ComplianceArtifactLink],
                      warnings: List[str], errors: List[ErrorInfo], log: str) -> GeometryDesignResult:
        return GeometryDesignResult(
            geometry_result_id=self._generate_id("GEO-RESULT", request.geometry_request_id),
            geometry_request_id=request.geometry_request_id,
            run_id=request.run_id,
            candidate_id=request.candidate_id,
            configuration_id=request.configuration_id,
            status=status,
            geometry_artifacts=artifacts,
            generated_components=components,
            mesh_validation=validation,
            trace_links=trace_links,
            compliance_artifact_links=comp_links,
            warnings=warnings,
            errors=errors,
            log=log
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        req_dict = state.get("geometry_design_request")
        if isinstance(req_dict, dict):
            req = GeometryDesignRequest(**req_dict)
        elif isinstance(req_dict, GeometryDesignRequest):
            req = req_dict
        else:
            state["geometry_design_result"] = None
            return state
            
        result = self.process_request(req)
        state["geometry_design_result"] = result
        return state
