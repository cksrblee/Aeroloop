import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
geom_id = vsp.AddGeom('FUSELAGE', '')
surf_id = vsp.GetXSecSurf(geom_id, 0)
vsp.ChangeXSecShape(surf_id, 1, vsp.XS_SUPER_ELLIPSE)
xsec_id = vsp.GetXSec(surf_id, 1)

try:
    parm_ids = vsp.GetXSecParmIDs(xsec_id)
    for pid in parm_ids:
        gn = vsp.GetParmGroupName(pid)
        if "XSecCurve" in gn:
            print(vsp.GetParmName(pid), gn)
except Exception as e:
    print(e)
    
