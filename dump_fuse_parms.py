import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
geom_id = vsp.AddGeom('FUSELAGE', '')

# Dump all parms by parsing GetParmName and GetParmGroupName from all parms
# Wait, FindContainers fails, so we need to get Parm IDs.
# For VSP3, we can get parms via FindContainerGroupNames or just iterate indices?
# Actually, we can use vsp.FindContainers? No, we got TypeError.
# Let's write them to a file by writing a vsp3 file and reading the XML? Yes! vsp3 is XML.
vsp.WriteVSPFile('test_fuse.vsp3')
print("Saved to test_fuse.vsp3")
