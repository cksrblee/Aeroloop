import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
print("Printing inputs for VSPAEROSweep:")
vsp.PrintAnalysisInputs("VSPAEROSweep")
