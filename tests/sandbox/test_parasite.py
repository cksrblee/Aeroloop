import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.ExecAnalysis("ParasiteDrag")
results = vsp.FindResultsID("Parasite_Drag_Summary")
print("Total CD0:", vsp.GetDoubleResults(results, "Total_CD")[0])
