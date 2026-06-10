import os
from pathlib import Path
from aeroloop.gui.components.visualization import plot_aerodynamics_polar, plot_geometry_areas

def test_visualizer_latest_run():
    base_dir = Path("/root/projects/AeroLoop/results/default_user")
    
    # Get all RUN directories sorted by modification time
    run_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("RUN-")], key=os.path.getmtime)
    if not run_dirs:
        print("No RUN directories found!")
        return
        
    latest_run = run_dirs[-1]
    print(f"Testing visualizer against latest run: {latest_run.name}")
    
    # Check aerodynamics polar
    aero_dir = latest_run / "aerodynamics_output"
    polar_files = list(aero_dir.glob("*.polar"))
    if polar_files:
        polar_path = str(polar_files[-1])
        print(f"  Found polar file: {polar_path}")
        try:
            fig_polar = plot_aerodynamics_polar(polar_path)
            print("  [SUCCESS] plot_aerodynamics_polar returned a Figure")
            # Verify it's not the 'Awaiting Data...' empty figure
            has_data = len(fig_polar.data) > 0
            if has_data:
                print("  [SUCCESS] Polar figure contains data traces.")
            else:
                print("  [WARNING] Polar figure is empty (Awaiting Data or parse failed).")
        except Exception as e:
            print(f"  [ERROR] plot_aerodynamics_polar threw an exception: {e}")
    else:
        print("  [SKIP] No polar files found in aerodynamics_output.")

    # Check geometry csv
    geo_dir = latest_run / "geometry_output"
    csv_files = list(geo_dir.glob("*_CompGeom.csv"))
    if csv_files:
        csv_path = str(csv_files[-1])
        print(f"  Found geometry CSV file: {csv_path}")
        try:
            fig_geo = plot_geometry_areas(csv_path)
            print("  [SUCCESS] plot_geometry_areas returned a Figure")
            # Verify it's not the 'Awaiting Data...' empty figure
            has_data = len(fig_geo.data) > 0
            if has_data:
                print("  [SUCCESS] Geometry figure contains data traces.")
            else:
                print("  [WARNING] Geometry figure is empty (Awaiting Data or parse failed).")
        except Exception as e:
            print(f"  [ERROR] plot_geometry_areas threw an exception: {e}")
    else:
        print("  [SKIP] No geometry CSV files found in geometry_output.")

if __name__ == "__main__":
    test_visualizer_latest_run()
