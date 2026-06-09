import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.ComputeMassProps(0, 100, 0)

# get all results
names = vsp.GetAllResultsNames()
print("All result names:", names)

