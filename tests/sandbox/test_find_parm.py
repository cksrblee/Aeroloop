import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
w = vsp.AddGeom("WING")
with open("parms.txt", "w") as f:
    for p in vsp.FindGeoms():
        pass
