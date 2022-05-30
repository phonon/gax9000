"""
Define interface for measurement sweeps.
"""
import logging
import json
from abc import ABC, abstractmethod

# list of available sweep types (hardcoded)
MEASUREMENT_SWEEPS = [
    "array",
    "single",
]


class MeasurementSweep(ABC):
    """Interface for measurement sweeps."""

    # sweep name, must match name in `get(name)`
    name = None
    
    @staticmethod
    def export_metadata(
        path,
        user,
        sweep,
        sweep_config,
        die_x,
        die_y,
        device_row,
        device_col,
        device_dx,
        device_dy,
        data_folder,
        program_name,
        program_config,
    ):
        metadata = {
            "user": user,
            "sweep": sweep,
            "sweep_config": sweep_config,
            "die_x": die_x,
            "die_y": die_y,
            "device_row": device_row,
            "device_col": device_col,
            "device_dx": device_dx,
            "device_dy": device_dy,
            "data_folder": data_folder,
            "program": program_name,
            "program_config": program_config,
        }

        with open(path, "w+") as f:
            json.dump(metadata, f, indent=2)
    
    @staticmethod
    @abstractmethod
    def default_config():
        """Return default `sweep_config` argument in `run` as a dict."""
        return {}
    
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
    
    @staticmethod
    def get(name):
        """Get measurement sweep class by name."""
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