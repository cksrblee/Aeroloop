"""
This module defines and organizes the charts to be generated for AeroLoop reports.
It is based on an analysis of the available plotting capabilities in the SUAVE module.

SUAVE categorizes plots into Performance (Mission, Airfoil, Propeller) and Geometry.
Here, they have been reorganized into logical categories for report generation.
"""

from enum import Enum, auto

class ChartCategory(Enum):
    MISSION_PERFORMANCE = auto()
    AERODYNAMICS = auto()
    PROPULSION = auto()
    ENERGY_BATTERY = auto()
    NOISE = auto()
    GEOMETRY = auto()
    AIRFOIL_ANALYSIS = auto()

class ChartType(Enum):
    # ==========================================
    # Mission & Flight Performance
    # ==========================================
    ALTITUDE_SFC_WEIGHT = ("Altitude, SFC, and Weight over Time", ChartCategory.MISSION_PERFORMANCE)
    AIRCRAFT_VELOCITIES = ("Aircraft Velocities", ChartCategory.MISSION_PERFORMANCE)
    FUEL_USE = ("Fuel Burnt over Time", ChartCategory.MISSION_PERFORMANCE)
    FLIGHT_CONDITIONS = ("Flight Conditions (Mach, Reynolds, etc.)", ChartCategory.MISSION_PERFORMANCE)
    FLIGHT_TRAJECTORY = ("Flight Trajectory Profile", ChartCategory.MISSION_PERFORMANCE)

    # ==========================================
    # Aerodynamics
    # ==========================================
    AERO_COEFFICIENTS = ("Aerodynamic Coefficients (CL, CD, etc.)", ChartCategory.AERODYNAMICS)
    AERO_FORCES = ("Aerodynamic Forces (Lift, Drag, Thrust, Weight)", ChartCategory.AERODYNAMICS)
    DRAG_COMPONENTS = ("Drag Components (Parasite, Induced, Compressibility)", ChartCategory.AERODYNAMICS)
    STABILITY_COEFFICIENTS = ("Stability Coefficients", ChartCategory.AERODYNAMICS)
    LIFT_DISTRIBUTION = ("Sectional Lift Distribution", ChartCategory.AERODYNAMICS)
    SURFACE_PRESSURE = ("Surface Pressure Contours", ChartCategory.AERODYNAMICS)

    # ==========================================
    # Propulsion
    # ==========================================
    DISC_POWER_LOADING = ("Disc Power Loading", ChartCategory.PROPULSION)
    PROPELLER_CONDITIONS = ("Propeller Operating Conditions", ChartCategory.PROPULSION)
    TILTROTOR_CONDITIONS = ("Tiltrotor Operating Conditions", ChartCategory.PROPULSION)
    EMOTOR_PROP_EFFICIENCY = ("eMotor & Propeller Efficiencies", ChartCategory.PROPULSION)
    LIFT_CRUISE_NETWORK = ("Lift-Cruise Network Performance", ChartCategory.PROPULSION)
    PROPELLER_DISC_INFLOW = ("Propeller Disc Inflow", ChartCategory.PROPULSION)
    PROPELLER_DISC_PERFORMANCE = ("Propeller Disc Performance", ChartCategory.PROPULSION)

    # ==========================================
    # Energy & Battery
    # ==========================================
    BATTERY_PACK_CONDITIONS = ("Battery Pack Conditions (Voltage, Current, Temp)", ChartCategory.ENERGY_BATTERY)
    BATTERY_CELL_CONDITIONS = ("Battery Cell Conditions", ChartCategory.ENERGY_BATTERY)
    BATTERY_DEGRADATION = ("Battery Degradation", ChartCategory.ENERGY_BATTERY)
    SOLAR_FLUX = ("Solar Flux", ChartCategory.ENERGY_BATTERY)

    # ==========================================
    # Noise
    # ==========================================
    GROUND_NOISE_LEVELS = ("Ground Sideline Noise Levels", ChartCategory.NOISE)
    FLIGHT_PROFILE_NOISE = ("Flight Profile Noise Contours", ChartCategory.NOISE)

    # ==========================================
    # Geometry & Visualizations
    # ==========================================
    VEHICLE_GEOMETRY = ("Vehicle 3D Geometry", ChartCategory.GEOMETRY)
    VEHICLE_VLM_PANELS = ("Vehicle VLM Panelization", ChartCategory.GEOMETRY)
    AIRFOIL_GEOMETRY = ("Airfoil Geometry", ChartCategory.GEOMETRY)
    PROPELLER_GEOMETRY = ("Propeller Geometry", ChartCategory.GEOMETRY)

    # ==========================================
    # Airfoil Specific Analysis
    # ==========================================
    AIRFOIL_BOUNDARY_LAYER = ("Airfoil Boundary Layer Properties", ChartCategory.AIRFOIL_ANALYSIS)
    AIRFOIL_SURFACE_FORCES = ("Airfoil Surface Forces", ChartCategory.AIRFOIL_ANALYSIS)
    AIRFOIL_POLARS = ("Airfoil Polars (CL vs CD, CL vs Alpha, etc.)", ChartCategory.AIRFOIL_ANALYSIS)

    def __init__(self, description: str, category: ChartCategory):
        self.description = description
        self.category = category

# ----------------------------------------------------------------------
# Helper / Wrapper function stubs to generate these charts
# ----------------------------------------------------------------------

def generate_chart(chart_type: ChartType, results, save_path: str, **kwargs):
    """
    Main entry point to generate a specific chart using SUAVE plots underneath.
    
    Args:
        chart_type (ChartType): The type of chart to generate.
        results: The SUAVE results data structure.
        save_path (str): File path to save the generated chart.
        kwargs: Additional arguments such as vehicle data or specific plot formatting.
    """
    pass

