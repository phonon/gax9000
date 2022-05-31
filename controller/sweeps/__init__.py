"""
Define interface for measurement sweeps.
"""
import logging
import json
import os
from abc import ABC, abstractmethod
from controller.programs import MeasurementProgram
from controller.sse import EventChannel
from controller.util import timestamp, np_dict_to_list_dict
from controller.util.io import export_hdf5, export_mat


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
    def metadata(
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
        return {
            "timestamp": timestamp(),
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
    
    @staticmethod
    def run_single(
        user: str,
        sweep_name: str,
        sweep_config: dict,
        die_x: int,
        die_y: int,
        device_row: int,
        device_col: int,
        device_dx: float,
        device_dy: float,
        data_folder: str,
        save_dir: str,
        save_data: bool,
        program: MeasurementProgram,
        program_config: dict,
        monitor_channel: EventChannel,
    ):
        """Standard internal method to run a program sweep on a single device
        inside a 2D array of devices. This method used internally by array sweep
        and single sweep. 
        """
        result = program.run(**program_config)
        
        sweep_metadata = MeasurementSweep.metadata(
            user=user,
            sweep=sweep_name,
            sweep_config=sweep_config,
            die_x=die_x,
            die_y=die_y,
            device_row=device_row,
            device_col=device_col,
            device_dx=device_dx,
            device_dy=device_dy,
            data_folder=data_folder,
            program_name=program.name,
            program_config=program_config,
        )
        
        if save_data and os.path.exists(data_folder):
            path_dir = os.path.join(data_folder, save_dir)
            os.makedirs(path_dir, exist_ok=True)

            path_meta = os.path.join(path_dir, "meta.json")
            path_result_h5 = os.path.join(path_dir, f"{program.name}.h5")
            path_result_mat = os.path.join(path_dir, f"{program.name}.mat")
            
            with open(path_meta, "w+") as f:
                json.dump(sweep_metadata, f, indent=2)
            export_hdf5(path_result_h5, result)
            export_mat(path_result_mat, result)
        
        # broadcast metadata and data
        if monitor_channel is not None:
            monitor_channel.publish({
                "metadata": sweep_metadata,
                "data": np_dict_to_list_dict(result), # converts np ndarrays to regular lists
            })

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
        device_dx,
        device_dy,
        device_row,
        device_col,
        data_folder,
        program,
        program_config,
        instr_b1500=None,
        instr_cascade=None,
        move_chuck=None, # callback to move chuck (x, y) relative to home (start position)
        monitor_channel=None,
        signal_cancel=None,
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