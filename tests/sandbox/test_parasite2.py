import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.ExecAnalysis("ParasiteDrag")
names = vsp.GetAllResultsNames()
print("Result names:", names)
for n in names:
    try:
        results = vsp.FindResultsID(n)
        print(f"Data for {n}:", vsp.GetAllDataNames(results))
    except:
        pass
