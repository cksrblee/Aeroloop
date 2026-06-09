import os
import tempfile
from typing import Dict, Any, List, Optional
import shutil

class VSPAeroRunner:
    def __init__(self, vspaero_path: Optional[str] = None):
        try:
            import openvsp as vsp
            self.vsp = vsp
        except ImportError:
            raise RuntimeError("OpenVSP Python API is not available.")
            
        self.vspaero_path = vspaero_path
        self.validate_openvsp_installation()

    def validate_openvsp_installation(self):
        """Initializes OpenVSP and checks for VSPAERO executable."""
        self.vsp.VSPCheckSetup()
        
        # If path provided, set and check
        if self.vspaero_path:
            if not self.vsp.CheckForVSPAERO(self.vspaero_path):
                print(f"Warning: VSPAERO executable not found at {self.vspaero_path}")
            self.vsp.SetVSPAEROPath(self.vspaero_path)
        else:
            # Fallback path if none provided (from previous agent implementation)
            fallback_path = "/root/anaconda3/envs/aero/bin"
            if self.vsp.CheckForVSPAERO(fallback_path):
                self.vsp.SetVSPAEROPath(fallback_path)

    def load_or_generate_vsp3(self, vsp3_path: str):
        """Loads a .vsp3 file into the OpenVSP workspace."""
        if not os.path.exists(vsp3_path):
            raise FileNotFoundError(f"Geometry file not found: {vsp3_path}")
            
        self.vsp.ClearVSPModel()
        self.vsp.ReadVSPFile(vsp3_path)
        self.vsp.Update()

    def run_compute_geometry(self, analysis_method: int = None) -> str:
        """Runs VSPAEROComputeGeometry to prepare mesh/panels."""
        comp_name = "VSPAEROComputeGeometry"
        self.vsp.SetAnalysisInputDefaults(comp_name)

        if analysis_method is None:
            analysis_method = self.vsp.VORTEX_LATTICE
            
        method = list(self.vsp.GetIntAnalysisInput(comp_name, "AnalysisMethod"))
        method[0] = analysis_method
        self.vsp.SetIntAnalysisInput(comp_name, "AnalysisMethod", method)

        comp_res_id = self.vsp.ExecAnalysis(comp_name)
        return comp_res_id

    def run_vspaero_sweep(self, 
                          alpha_range: List[float],
                          mach_range: List[float],
                          geom_set: int = 0,
                          ref_flag: int = 1,
                          wing_id: Optional[str] = None,
                          ncpu: int = 4,
                          redirect_file: str = "vspaero.log",
                          extra_configs: Dict[str, Any] = None) -> str:
        """Runs VSPAEROSweep with the specified conditions."""
        sweep_name = "VSPAEROSweep"
        self.vsp.SetAnalysisInputDefaults(sweep_name)

        self.vsp.SetIntAnalysisInput(sweep_name, "GeomSet", [geom_set], 0)

        if wing_id:
            self.vsp.SetIntAnalysisInput(sweep_name, "RefFlag", [ref_flag], 0)
            self.vsp.SetStringAnalysisInput(sweep_name, "WingID", [wing_id], 0)
            
        # Set Alpha
        if alpha_range:
            self.vsp.SetDoubleAnalysisInput(sweep_name, "AlphaStart", [alpha_range[0]], 0)
            self.vsp.SetDoubleAnalysisInput(sweep_name, "AlphaEnd", [alpha_range[-1]], 0)
            self.vsp.SetIntAnalysisInput(sweep_name, "AlphaNpts", [len(alpha_range)], 0)
            
        # Set Mach
        if mach_range:
            self.vsp.SetDoubleAnalysisInput(sweep_name, "MachStart", [mach_range[0]], 0)
            self.vsp.SetDoubleAnalysisInput(sweep_name, "MachEnd", [mach_range[-1]], 0)
            self.vsp.SetIntAnalysisInput(sweep_name, "MachNpts", [len(mach_range)], 0)
            
        # Optional runtime controls
        self.vsp.SetIntAnalysisInput(sweep_name, "NCPU", [ncpu], 0)
        self.vsp.SetStringAnalysisInput(sweep_name, "RedirectFile", [redirect_file], 0)
        
        # Additional extra_configs (e.g. GroundEffectToggle, ClmaxToggle)
        if extra_configs:
            for k, v in extra_configs.items():
                # Just simple typing check for Double vs Int based on type, string ignored
                if isinstance(v, list) and len(v) > 0:
                    if isinstance(v[0], float):
                        self.vsp.SetDoubleAnalysisInput(sweep_name, k, v, 0)
                    elif isinstance(v[0], int):
                        self.vsp.SetIntAnalysisInput(sweep_name, k, v, 0)
                    elif isinstance(v[0], str):
                        self.vsp.SetStringAnalysisInput(sweep_name, k, v, 0)
                else:
                    if isinstance(v, float):
                        self.vsp.SetDoubleAnalysisInput(sweep_name, k, [v], 0)
                    elif isinstance(v, int):
                        self.vsp.SetIntAnalysisInput(sweep_name, k, [v], 0)
                    elif isinstance(v, str):
                        self.vsp.SetStringAnalysisInput(sweep_name, k, [v], 0)

        self.vsp.Update()
        sweep_res_id = self.vsp.ExecAnalysis(sweep_name)
        return sweep_res_id
