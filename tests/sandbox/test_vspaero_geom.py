import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

print("Running VSPAEROComputeGeometry...")
vsp.SetAnalysisInputDefaults("VSPAEROComputeGeometry")
vsp.SetStringAnalysisInput("VSPAEROComputeGeometry", "GeomID", [wing_id])
vsp.ExecAnalysis("VSPAEROComputeGeometry")

print("Running VSPAEROSweep...")
vsp.SetAnalysisInputDefaults("VSPAEROSweep")
vsp.SetIntAnalysisInput("VSPAEROSweep", "AlphaNpts", [1])
vsp.SetDoubleAnalysisInput("VSPAEROSweep", "AlphaStart", [5.0])
vsp.SetStringAnalysisInput("VSPAEROSweep", "WingID", [wing_id])
vsp.ExecAnalysis("VSPAEROSweep")

names = vsp.GetAllResultsNames()
print("Result names:", names)
