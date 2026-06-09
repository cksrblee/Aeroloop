import sys
import os
import subprocess
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()
fuse_id = vsp.AddGeom("FUSELAGE")
wing_id = vsp.AddGeom("WING")

print("Exporting DegenGeom CSV...")
vsp.ExportFile("test_model.csv", vsp.SET_ALL, vsp.DEGEN_GEOM_CSV_TYPE)

setup_content = """Sref = 100.0
Cref = 1.0
Bref = 1.0
X_cg = 0.0
Y_cg = 0.0
Z_cg = 0.0
Mach = 0.0
AoA = 5.0
Beta = 0.0
Vinf = 100.0
Rho = 0.002377
ReCref = 10000000.0
Symmetry = 0
FarDist = -1.0
NumWakeNodes = 8
WakeIters = 5
"""
with open("test_model.vspaero", "w") as f:
    f.write(setup_content)

print("Running vspaero...")
res = subprocess.run(["/root/anaconda3/envs/aero/bin/vspaero", "-omp", "4", "test_model"], capture_output=True, text=True)
print(res.stdout[-500:])

if os.path.exists("test_model.history"):
    with open("test_model.history", "r") as f:
        print(f.read())
