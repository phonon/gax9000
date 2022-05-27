"""
Define interface for measurement sweeps.
"""
import logging
from abc import ABC, abstractmethod

# list of available sweep types (hardcoded)
MEASUREMENT_SWEEPS = [
    "array",
    "single",
]

def get_measurement_sweep(name):
    """Return sweep by name."""
    s = name.lower()
    if s == "array":
        from controller.sweeps.array import SweepArray
        return SweepArray
    elif s == "single":
        from controller.sweeps.single import SweepSingle
        return SweepSingle
    else:
        logging.error(f"Unknown sweep type: {name}")
        return None


class MeasurementSweep(ABC):
    """Interface for measurement sweeps."""
    
    @staticmethod
    @abstractmethod
    def run(
        user,
        sweep_config,
        sweep_save_data,
        current_die_x,
        current_die_y,
        device_x,
        device_y,
        device_row,
        device_col,
        data_folder,
        program,
        program_config,
    ):
        """Run the sweep."""
        pass