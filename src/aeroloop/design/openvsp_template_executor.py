"""
Template-driven OpenVSP builder for GeometryDesignAgent.

This file is intentionally conservative:
- it applies raw OpenVSP Parm entries when they exist;
- it warns instead of crashing for optional missing Parm names;
- it supports FUSELAGE/WING/POD/PROP/etc. through AddGeom;
- it supports XSec shape changes when the installed OpenVSP exposes the requested constants;
- it can dump all available OpenVSP geometry types and Parm names from the local installation.

Use it as a starting point and move the functions into GeometryDesignAgent or a
separate aeroloop/utils/openvsp_template.py module.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class TemplateBuildReport:
    geom_ids: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unmatched_parms: List[Dict[str, Any]] = field(default_factory=list)
    applied_parms: List[Dict[str, Any]] = field(default_factory=list)


def load_openvsp_template(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if path.endswith(('.yaml', '.yml')):
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML templates. Install with: pip install pyyaml")
        return yaml.safe_load(text)
    return json.loads(text)


def resolve_value(spec: Dict[str, Any], design_parameters: Dict[str, Any], vsp: Any = None) -> Any:
    """Resolve value/value_ref/default/value_enum in a raw_vsp_parm spec."""
    if "value_enum" in spec:
        enum_name = spec["value_enum"]
        if vsp is not None and hasattr(vsp, enum_name):
            return getattr(vsp, enum_name)
        return enum_name

    if "value_ref" in spec:
        key = spec["value_ref"]
        if key in design_parameters:
            val = design_parameters[key]
        elif "default" in spec:
            val = spec["default"]
        else:
            raise KeyError(f"Missing design parameter: {key}")
    elif "value" in spec:
        val = spec["value"]
    elif "default" in spec:
        val = spec["default"]
    else:
        val = None

    # Optional numeric scale, useful for half-span, etc.
    if isinstance(val, (int, float)) and "scale" in spec:
        val = val * spec["scale"]
    return val


def _is_missing_parm_id(parm_id: Any) -> bool:
    return parm_id is None or parm_id == "" or parm_id == "NONE" or parm_id == "INVALID"


def safe_set_parm(
    vsp: Any,
    container_id: str,
    parm_spec: Dict[str, Any],
    design_parameters: Dict[str, Any],
    report: TemplateBuildReport,
    strict: bool = False,
    context: str = "",
) -> None:
    name = parm_spec.get("name")
    group = parm_spec.get("group")
    required = bool(parm_spec.get("required", False))

    if not name or not group:
        msg = f"Invalid parm spec without name/group in {context}: {parm_spec}"
        if strict or required:
            report.errors.append(msg)
        else:
            report.warnings.append(msg)
        return

    try:
        value = resolve_value(parm_spec, design_parameters, vsp=vsp)
    except Exception as exc:
        msg = f"Could not resolve value for {context}.{group}.{name}: {exc}"
        if strict or required:
            report.errors.append(msg)
        else:
            report.warnings.append(msg)
        return

    try:
        parm_id = ""
        if group in ("XSecCurve", "XSec"):
            try:
                parm_id = vsp.GetXSecParm(container_id, name)
            except Exception:
                pass
        if not parm_id:
            parm_id = vsp.FindParm(container_id, name, group)
    except Exception:
        parm_id = ""

    if _is_missing_parm_id(parm_id):
        entry = {"context": context, "container_id": container_id, "name": name, "group": group, "value": value}
        report.unmatched_parms.append(entry)
        msg = f"OpenVSP Parm not found: {context}.{group}.{name}"
        if strict or required:
            report.errors.append(msg)
        else:
            report.warnings.append(msg)
        return

    try:
        vsp.SetParmVal(parm_id, value)
        report.applied_parms.append({"context": context, "parm_id": parm_id, "name": name, "group": group, "value": value})
    except Exception as exc:
        msg = f"Failed SetParmVal for {context}.{group}.{name}={value}: {exc}"
        if strict or required:
            report.errors.append(msg)
        else:
            report.warnings.append(msg)


def apply_raw_parms(
    vsp: Any,
    container_id: str,
    raw_vsp_parms: List[Dict[str, Any]],
    design_parameters: Dict[str, Any],
    report: TemplateBuildReport,
    strict: bool = False,
    context: str = "",
) -> None:
    for parm_spec in raw_vsp_parms or []:
        safe_set_parm(vsp, container_id, parm_spec, design_parameters, report, strict=strict, context=context)


def apply_common_blocks(vsp: Any, geom_id: str, component: Dict[str, Any], template: Dict[str, Any], design_parameters: Dict[str, Any], report: TemplateBuildReport, strict: bool) -> None:
    common_blocks = template.get("common_parm_blocks", {})
    for block_name in component.get("apply_common_blocks", []) or []:
        block = common_blocks.get(block_name, {})
        apply_raw_parms(vsp, geom_id, block.get("raw_vsp_parms", []), design_parameters, report, strict=False, context=f"{component.get('name', 'component')}.{block_name}")


def apply_xsecs(vsp: Any, geom_id: str, component_name: str, component: Dict[str, Any], design_parameters: Dict[str, Any], report: TemplateBuildReport, strict: bool) -> None:
    for surf in component.get("xsec_surfaces", []) or []:
        surf_index = int(surf.get("surf_index", 0))
        try:
            xsec_surf_id = vsp.GetXSecSurf(geom_id, surf_index)
        except Exception as exc:
            report.warnings.append(f"Could not get XSecSurf for {component_name}[{surf_index}]: {exc}")
            continue

        for xsec in surf.get("xsecs", []) or []:
            idx = int(xsec.get("index", 0))
            shape_name = xsec.get("shape")
            if shape_name and hasattr(vsp, shape_name):
                try:
                    vsp.ChangeXSecShape(xsec_surf_id, idx, getattr(vsp, shape_name))
                except Exception as exc:
                    report.warnings.append(f"Could not ChangeXSecShape {component_name}[{idx}] to {shape_name}: {exc}")

            try:
                xsec_id = vsp.GetXSec(xsec_surf_id, idx)
            except Exception as exc:
                report.warnings.append(f"Could not get XSec {component_name}[{idx}]: {exc}")
                continue

            apply_raw_parms(
                vsp,
                xsec_id,
                xsec.get("raw_vsp_parms", []),
                design_parameters,
                report,
                strict=strict,
                context=f"{component_name}.xsec[{idx}]",
            )


def add_subsurfaces(vsp: Any, geom_id: str, component_name: str, component: Dict[str, Any], design_parameters: Dict[str, Any], report: TemplateBuildReport, strict: bool) -> None:
    for block_name in ("subsurfaces", "control_surfaces"):
        for ss in component.get(block_name, []) or []:
            type_name = ss.get("type")
            if not type_name or not hasattr(vsp, type_name):
                report.warnings.append(f"Skipping {component_name}.{block_name}.{ss.get('name')}: unknown type {type_name}")
                continue
            try:
                ss_id = vsp.AddSubSurf(geom_id, getattr(vsp, type_name), 0)
            except Exception as exc:
                report.warnings.append(f"Could not AddSubSurf for {component_name}.{ss.get('name')}: {exc}")
                continue
            apply_raw_parms(vsp, ss_id, ss.get("raw_vsp_parms", []), design_parameters, report, strict=strict, context=f"{component_name}.{ss.get('name')}")


def instantiate_component_entries(component_name: str, component: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Expand array_instances into per-component dicts."""
    if not component.get("instantiate_as_array"):
        comp = deepcopy(component)
        comp["name"] = component_name
        return [(component_name, comp)]

    entries: List[Tuple[str, Dict[str, Any]]] = []
    for inst in component.get("array_instances", []) or []:
        inst_name = inst.get("name", component_name)
        comp = deepcopy(component)
        comp["name"] = inst_name
        comp.setdefault("transform_overrides", {}).setdefault("raw_vsp_parms", [])
        comp["transform_overrides"]["raw_vsp_parms"].extend([
            {"name": "X_Rel_Location", "group": "XForm", "value": inst.get("x", 0.0), "required": False},
            {"name": "Y_Rel_Location", "group": "XForm", "value": inst.get("y", 0.0), "required": False},
            {"name": "Z_Rel_Location", "group": "XForm", "value": inst.get("z", 0.0), "required": False},
            {"name": "Z_Rel_Rotation", "group": "XForm", "value": inst.get("rotation_z", 0.0), "required": False},
        ])
        entries.append((inst_name, comp))
    return entries


def build_openvsp_from_template(vsp: Any, template: Dict[str, Any], design_parameters: Optional[Dict[str, Any]] = None) -> TemplateBuildReport:
    """Create OpenVSP geometry from a registry template."""
    report = TemplateBuildReport()
    design_parameters = {**template.get("design_parameters", {}), **(design_parameters or {})}
    runtime = template.get("runtime", {})
    strict = bool(runtime.get("strict_parameter_matching", False))

    if runtime.get("renew_workspace", True):
        vsp.VSPRenew()

    available_types = None
    if runtime.get("validate_geom_type_available", True) and hasattr(vsp, "GetGeomTypes"):
        try:
            available_types = set(vsp.GetGeomTypes())
        except Exception as exc:
            report.warnings.append(f"Could not query GetGeomTypes: {exc}")

    for component_key, component_def in (template.get("components", {}) or {}).items():
        if not component_def.get("enabled", True):
            continue

        for component_name, component in instantiate_component_entries(component_key, component_def):
            geom_type = component.get("geom_type")
            if available_types is not None and geom_type not in available_types:
                msg = f"OpenVSP Geom type not available in local install: {geom_type} for {component_name}"
                if strict:
                    report.errors.append(msg)
                    continue
                report.warnings.append(msg)

            parent_key = component.get("parent")
            parent_id = report.geom_ids.get(parent_key, "") if parent_key else ""
            try:
                geom_id = vsp.AddGeom(geom_type, parent_id)
            except TypeError:
                geom_id = vsp.AddGeom(geom_type)
            except Exception as exc:
                report.errors.append(f"AddGeom failed for {component_name} ({geom_type}): {exc}")
                continue

            report.geom_ids[component_name] = geom_id
            if hasattr(vsp, "SetGeomName"):
                try:
                    vsp.SetGeomName(geom_id, component_name)
                except Exception:
                    pass

            if component.get("material") and hasattr(vsp, "SetGeomMaterialName"):
                try:
                    vsp.SetGeomMaterialName(geom_id, component["material"])
                except Exception as exc:
                    report.warnings.append(f"Could not set material for {component_name}: {exc}")

            apply_common_blocks(vsp, geom_id, component, template, design_parameters, report, strict)
            apply_raw_parms(vsp, geom_id, component.get("transform_overrides", {}).get("raw_vsp_parms", []), design_parameters, report, strict=False, context=f"{component_name}.transform_overrides")
            apply_raw_parms(vsp, geom_id, component.get("raw_vsp_parms", []), design_parameters, report, strict=strict, context=component_name)
            apply_xsecs(vsp, geom_id, component_name, component, design_parameters, report, strict)
            add_subsurfaces(vsp, geom_id, component_name, component, design_parameters, report, strict)

            if runtime.get("update_after_each_component", True):
                try:
                    vsp.Update()
                except Exception as exc:
                    report.warnings.append(f"OpenVSP Update failed after {component_name}: {exc}")

    try:
        vsp.Update()
    except Exception as exc:
        report.warnings.append(f"Final OpenVSP Update failed: {exc}")

    return report


def export_from_template(vsp: Any, template: Dict[str, Any], output_dir: str, candidate_id: str, report: TemplateBuildReport) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    artifacts: Dict[str, str] = {}
    export_options = template.get("export_options", {})

    if export_options.get("write_vsp3", True):
        vsp3_path = os.path.join(output_dir, f"{candidate_id}.vsp3")
        vsp.WriteVSPFile(vsp3_path)
        artifacts["vsp3"] = vsp3_path
        
    analysis_options = template.get("analysis_options", {})
    comp_geom_opts = analysis_options.get("comp_geom", {})
    if comp_geom_opts.get("enabled", False) and comp_geom_opts.get("output_csv", False):
        csv_path = os.path.join(output_dir, f"{candidate_id}_CompGeom.csv")
        try:
            vsp.SetComputationFileName(vsp.COMP_GEOM_CSV_TYPE, csv_path)
            vsp.ComputeCompGeom(vsp.SET_ALL, False, vsp.COMP_GEOM_CSV_TYPE)
            artifacts["comp_geom_csv"] = csv_path
        except Exception as exc:
            report.errors.append(f"CompGeom CSV export failed: {exc}")

    for fmt_name, fmt in (export_options.get("formats", {}) or {}).items():
        if not fmt.get("enabled", False):
            continue
        const_name = fmt.get("export_constant")
        if not const_name or not hasattr(vsp, const_name):
            report.warnings.append(f"Skipping export {fmt_name}: missing OpenVSP constant {const_name}")
            continue
        path = os.path.join(output_dir, f"{candidate_id}{fmt.get('file_suffix', '.' + fmt_name)}")
        try:
            vsp.ExportFile(path, vsp.SET_ALL, getattr(vsp, const_name))
            artifacts[fmt_name] = path
        except Exception as exc:
            report.errors.append(f"Export failed for {fmt_name}: {exc}")

    manifest_path = os.path.join(output_dir, f"{candidate_id}_openvsp_template_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "geom_ids": report.geom_ids,
            "warnings": report.warnings,
            "errors": report.errors,
            "unmatched_parms": report.unmatched_parms,
            "applied_parms": report.applied_parms,
            "artifacts": artifacts,
        }, f, indent=2, ensure_ascii=False)
    artifacts["template_manifest"] = manifest_path
    return artifacts


def dump_local_openvsp_catalog(vsp: Any, output_json: str) -> Dict[str, Any]:
    """Dump geometry types and their Parm names/groups from the installed OpenVSP.

    This is the practical way to get the closest thing to 'all options', because
    OpenVSP parameters differ by Geom type, XSec type, and version.
    """
    catalog: Dict[str, Any] = {"geom_types": {}}
    vsp.VSPRenew()
    try:
        geom_types = list(vsp.GetGeomTypes())
    except Exception:
        geom_types = ["FUSELAGE", "WING", "POD", "PROP", "STACK", "DUCT", "BOR", "CONFORMAL", "HUMAN"]

    for geom_type in geom_types:
        try:
            geom_id = vsp.AddGeom(geom_type, "")
            vsp.Update()
            parms = []
            for pid in list(vsp.GetGeomParmIDs(geom_id)):
                item = {"parm_id": pid}
                for fn_name, key in [
                    ("GetParmName", "name"),
                    ("GetParmGroupName", "group"),
                    ("GetParmDisplayGroupName", "display_group"),
                    ("GetParmDescript", "description"),
                    ("GetParmVal", "value"),
                    ("GetParmLowerLimit", "lower"),
                    ("GetParmUpperLimit", "upper"),
                    ("GetParmType", "type"),
                ]:
                    if hasattr(vsp, fn_name):
                        try:
                            item[key] = getattr(vsp, fn_name)(pid)
                        except Exception:
                            pass
                parms.append(item)
            catalog["geom_types"][geom_type] = {"parms": parms}
            try:
                vsp.DeleteGeom(geom_id)
            except Exception:
                pass
        except Exception as exc:
            catalog["geom_types"][geom_type] = {"error": str(exc)}

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    return catalog
