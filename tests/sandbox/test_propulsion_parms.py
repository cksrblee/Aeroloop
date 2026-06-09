import sys
sys.path.insert(0, '/root/projects/AeroLoop/thirdparty/build_openvsp/OpenVSP-prefix/src/OpenVSP-build/python_pseudo/openvsp')
import openvsp as vsp

vsp.VSPRenew()

def check_parm(geom_id, name, group):
    try:
        p = vsp.FindParm(geom_id, name, group)
        if p != "":
            print(f"[OK] {group} {name}")
        else:
            print(f"[FAIL] {group} {name} (returned empty)")
    except Exception as e:
        print(f"[FAIL] {group} {name}: {e}")

print("--- PROP ---")
prop_id = vsp.AddGeom('PROP', '')
check_parm(prop_id, "Diameter", "Design")
check_parm(prop_id, "NumBlade", "Design")
check_parm(prop_id, "BladeNum", "Design")
check_parm(prop_id, "Beta34", "Design")
check_parm(prop_id, "Feather", "Design")
check_parm(prop_id, "ReverseFlag", "Design")
check_parm(prop_id, "Chord", "Prop_0")
check_parm(prop_id, "Twist", "Prop_0")
check_parm(prop_id, "Rake", "Prop_0")
check_parm(prop_id, "Skew", "Prop_0")

print("\n--- POD ---")
pod_id = vsp.AddGeom('POD', '')
check_parm(pod_id, "Length", "Design")
check_parm(pod_id, "Diameter", "Design")
check_parm(pod_id, "FineRatio", "Design")

print("\n--- DUCT ---")
duct_id = vsp.AddGeom('DUCT', '')
check_parm(duct_id, "Diameter", "Design")
check_parm(duct_id, "Length", "Design")
check_parm(duct_id, "Inlet_Dia", "Design")
check_parm(duct_id, "Exit_Dia", "Design")

