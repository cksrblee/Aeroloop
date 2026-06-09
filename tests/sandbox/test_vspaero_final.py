import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

vsp.SetAnalysisInputDefaults("VSPAEROSweep")
vsp.SetIntAnalysisInput("VSPAEROSweep", "AlphaNpts", [1])
vsp.SetStringAnalysisInput("VSPAEROSweep", "WingID", [wing_id])
vsp.ExecAnalysis("VSPAEROSweep")
names = vsp.GetAllResultsNames()
print("Result names:", names)
