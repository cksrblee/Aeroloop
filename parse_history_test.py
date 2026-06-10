import sys

def parse_history(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    cases = []
    current_case = []
    
    # We look for lines that contain integers in the first column
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        try:
            iter_num = int(parts[0])
            current_case.append(parts)
        except ValueError:
            # Not a data line. If we have accumulated a case, save it.
            if current_case:
                cases.append(current_case)
                current_case = []
    if current_case:
        cases.append(current_case)
        
    alpha, mach, cl, cd, cm = [], [], [], [], []
    for case in cases:
        last_row = case[-1] # The converged iteration for this case
        mach.append(float(last_row[1]))
        alpha.append(float(last_row[2]))
        cl.append(float(last_row[6]))
        cd.append(float(last_row[9]))
        cm.append(float(last_row[22]))
        
    print(f"Alpha: {alpha}")
    print(f"Mach: {mach}")
    print(f"CL: {cl}")
    print(f"CD: {cd}")
    print(f"CM: {cm}")

parse_history('/root/projects/AeroLoop/results/default_user/RUN-df5e52ed/aerodynamics_output/AC-b582f56b.history')
