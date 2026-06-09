import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp
vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
xsec_surf_id = vsp.GetXSecSurf(fuse_id, 0)
xsec_id = vsp.GetXSec(xsec_surf_id, 1)

try:
    print("FindParm XLocPercent XSec:", vsp.FindParm(xsec_id, "XLocPercent", "XSec"))
except Exception as e:
    print(e)
try:
    print("GetXSecParm XLocPercent:", vsp.GetXSecParm(xsec_id, "XLocPercent"))
except Exception as e:
    print(e)
