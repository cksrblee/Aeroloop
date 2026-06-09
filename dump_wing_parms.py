import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
geom_id = vsp.AddGeom('WING', '')

parms = vsp.FindContainers(geom_id)
for p in parms:
    print(vsp.GetParmName(p), vsp.GetParmGroupName(p), vsp.GetParmVal(p))
