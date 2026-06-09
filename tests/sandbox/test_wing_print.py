import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
w = vsp.AddGeom("WING")
parm_ids = vsp.FindGeomParms(w)
for pid in parm_ids:
    name = vsp.GetParmName(pid)
    grp = vsp.GetParmGroupName(pid)
    if "Span" in name or "Area" in name:
        print(grp, name, vsp.GetParmVal(pid))
