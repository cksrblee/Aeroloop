import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
geom_id = vsp.AddGeom('FUSELAGE', '')
surf_id = vsp.GetXSecSurf(geom_id, 0)
xsec_id = vsp.GetXSec(surf_id, 1) # usually super_ellipse
vsp.ChangeXSecShape(surf_id, 1, vsp.XS_ELLIPSE)

print("XSec ID:", xsec_id)
# let's try to get Parm
p1 = vsp.FindParm(geom_id, "Width", "XSecCurve")
p2 = vsp.FindParm(xsec_id, "Width", "XSecCurve")

print("geom_id parm:", p1)
print("xsec_id parm:", p2)

# Maybe we need xsec curve?
curve_id = vsp.GetXSecCurve(surf_id, 1) # no wait, GetXSecCurve doesn't take surf_id? Let's use get_methods.
import inspect
print([m for m in dir(vsp) if 'XSecCurve' in m])

