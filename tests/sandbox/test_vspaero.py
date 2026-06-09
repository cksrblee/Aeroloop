import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

vsp.SetVSPAEROPath("/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp/openvsp/")

vsp.SetAnalysisInputDefaults("VSPAEROSweep")
vsp.SetIntAnalysisInput("VSPAEROSweep", "AlphaNum", [1])
vsp.SetDoubleAnalysisInput("VSPAEROSweep", "AlphaStart", [5.0])
vsp.SetIntAnalysisInput("VSPAEROSweep", "ReNum", [1])
vsp.SetDoubleAnalysisInput("VSPAEROSweep", "ReStart", [1000000.0])
vsp.SetIntAnalysisInput("VSPAEROSweep", "MachNum", [1])
vsp.SetDoubleAnalysisInput("VSPAEROSweep", "MachStart", [0.0])
vsp.SetStringAnalysisInput("VSPAEROSweep", "AnalysisMethod", ["VortexLattice"])

# Setup Reference
vsp.SetStringAnalysisInput("VSPAEROSweep", "GeomID", [wing_id])

print("Executing VSPAEROSweep...")
vsp.ExecAnalysis("VSPAEROSweep")

names = vsp.GetAllResultsNames()
print("All result names:", names)

if "VSPAERO_History" in names:
    res_id = vsp.FindResultsID("VSPAERO_History")
    try:
        print("CL:", vsp.GetDoubleResults(res_id, "CL"))
        print("CDtot:", vsp.GetDoubleResults(res_id, "CDtot"))
        print("L/D:", vsp.GetDoubleResults(res_id, "L_D"))
    except Exception as e:
        print(e)
