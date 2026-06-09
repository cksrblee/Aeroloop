import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

res = vsp.FindResultsID("ParasiteDrag")
print("ParasiteDrag initial:", res)

# Try running Parasite Drag
vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.ExecAnalysis("ParasiteDrag")

names = vsp.GetAllResultsNames()
print("All result names after ParasiteDrag:", names)
if "Parasite_Drag" in names:
    res_id = vsp.FindResultsID("Parasite_Drag")
    print(vsp.GetAllDataNames(res_id))

