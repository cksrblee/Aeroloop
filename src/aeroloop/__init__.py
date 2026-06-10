import sys
import os

# Globally ensure the correct OpenVSP Python API is used throughout the aeroloop package
vsp_path = "/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp"
if vsp_path not in sys.path:
    sys.path.insert(0, vsp_path)