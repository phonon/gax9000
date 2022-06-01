import os
import json
from controller.sweeps import MeasurementSweep
from controller.util import timestamp, np_dict_to_list_dict
from controller.util.io import export_hdf5, export_mat

class SweepSingle(MeasurementSweep):
    """Implement a single device sweep."""

    name = "single"

    def __repr__(self) -> str:
        return "SweepSingle"

    def __str__(self) -> str:
        return self.__repr__()

    def default_config():
        """Return default `sweep_config` argument in `run` as a dict."""
        return {
            "programs": [],
        }
    
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
        move_chuck=None,
        monitor_channel=None,
        signal_cancel=None,
    ):
        """Run the sweep. Just a wrapper around MeasurementSweep.run_single."""
        t_measurement = timestamp()
        save_dir = f"gax_r{device_row}_c{device_col}_{program.name}_{t_measurement}"

        MeasurementSweep.run_single(
            instr_b1500=instr_b1500,
            user=user,
            sweep_name=SweepSingle.name,
            sweep_config=sweep_config,
            die_x=current_die_x,
            die_y=current_die_y,
            device_row=device_row,
            device_col=device_col,
            device_dx=device_dx,
            device_dy=device_dy,
            data_folder=data_folder,
            save_dir=save_dir,
            save_data=sweep_save_data,
            program=program,
            program_config=program_config,
            monitor_channel=monitor_channel,
        )
