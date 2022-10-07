"""
Define interface for measurement sweeps.
"""
import logging
import json
import os
from abc import ABC, abstractmethod
from controller.programs import MeasurementProgram
from controller.sse import EventChannel
from controller.util import timestamp, dict_np_array_to_json_array, SignalCancelTask
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
        program_names,
        program_configs,
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
            "programs": program_names,
            "program_configs": program_configs,
        }
    
    @staticmethod
    def save_metadata(
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
        programs: list[MeasurementProgram],
        program_configs: list[dict],
    ) -> dict:
        """Save metadata `meta.json` file to save directory.
        Returns the metadata dict object.
        """
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
            program_names=[p.name for p in programs],
            program_configs=program_configs,
        )
        
        if save_data and os.path.exists(data_folder):
            path_dir = os.path.join(data_folder, save_dir)
            os.makedirs(path_dir, exist_ok=True)

            path_meta = os.path.join(path_dir, "meta.json")
            
            with open(path_meta, "w+") as f:
                json.dump(sweep_metadata, f, indent=2)
        
        return sweep_metadata

    @staticmethod
    def run_single(
        instr_b1500,
        monitor_channel: EventChannel,
        signal_cancel: SignalCancelTask,
        sweep_metadata: dict,
        data_folder: str,
        save_dir: str,
        save_data: bool,
        program: MeasurementProgram,
        program_config: dict,
    ):
        """Standard internal method to run a program sweep on a single device
        inside a 2D array of devices. This method used internally by array sweep
        and single sweep. This feeds program built-in args and user program 
        specific config args:

        Built-in config args:
        - `instr_b1500`: B1500 instrument object
        - `monitor_channel`: EventChannel object for sending status updates
        - `signal_cancel`: SignalCancelTask object for checking for user cancel signal
        - `sweep_metadata`: Copy of sweep metadata dict
        - `path_data_folder`: Path to overall sweep data folder, for programs that do continuous data saving
        - `path_save_dir`: Path to sweep specific data folder, for programs that do continuous data saving
        """
        result = program.run(
            instr_b1500=instr_b1500,
            monitor_channel=monitor_channel,
            signal_cancel=signal_cancel,
            sweep_metadata=sweep_metadata,
            path_data_folder=data_folder,
            path_save_dir=save_dir,
            **program_config,
        )
        
        if save_data and result.save_data and os.path.exists(data_folder):
            path_dir = os.path.join(data_folder, save_dir)
            os.makedirs(path_dir, exist_ok=True)

            path_result_h5 = os.path.join(path_dir, f"{program.name}.h5")
            path_result_mat = os.path.join(path_dir, f"{program.name}.mat")
            
            export_hdf5(path_result_h5, result.data)
            export_mat(path_result_mat, result.data)
        
        # broadcast metadata and data
        if monitor_channel is not None:
            monitor_channel.publish({
                "metadata": {
                    "program": program.name,
                    "config": sweep_metadata,
                },
                "data": dict_np_array_to_json_array(result.data), # converts np ndarrays to regular lists
            })

    @staticmethod
    @abstractmethod
    def default_config():
        """Return default `sweep_config` argument in `run` as a dict."""
        return {}
    
    @staticmethod
    @abstractmethod
    def run(
        user: str,
        sweep_config: dict,
        sweep_save_data: bool,
        current_die_x: int,
        current_die_y: int,
        device_dx: float,
        device_dy: float,
        device_row: int,
        device_col: int,
        data_folder: str,
        programs: list[MeasurementProgram],
        program_configs: list[dict],
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