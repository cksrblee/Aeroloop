import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
w = vsp.AddGeom("WING")
try:
    print("Span 1:", vsp.GetParmVal(vsp.GetGeomParm(w, "Span")))
except Exception as e:
    print("Span 1 failed", e)
try:
    print("Span 2:", vsp.GetParmVal(vsp.GetGeomParm(w, "Span", "Design")))
except Exception as e:
    print("Span 2 failed", e)
try:
    print("TotalArea:", vsp.GetParmVal(vsp.GetGeomParm(w, "TotalArea", "Plan")))
except Exception as e:
    print("TotalArea failed", e)
