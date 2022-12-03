import os
import json
import gevent
from controller.sweeps import MeasurementSweep
from controller.util import timestamp, dict_np_array_to_json_array
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
        initial_die_x,
        initial_die_y,
        die_dx,
        die_dy,
        initial_device_row,
        initial_device_col,
        device_dx,
        device_dy,
        data_folder,
        programs,
        program_configs,
        instr_b1500=None,
        instr_cascade=None,
        monitor_channel=None,
        signal_cancel=None,
    ):
        """Run the sweep. Just a wrapper around MeasurementSweep.run_single."""
        t_measurement = timestamp()
        save_dir = f"gax_r{initial_device_row}_c{initial_device_col}_{t_measurement}"

        sweep_metadata = MeasurementSweep.save_metadata(
            user=user,
            sweep_name=SweepSingle.name,
            sweep_config=sweep_config,
            initial_die_x=initial_die_x,
            initial_die_y=initial_die_y,
            die_dx=die_dx,
            die_dy=die_dy,
            initial_device_row=initial_device_row,
            initial_device_col=initial_device_col,
            device_dx=device_dx,
            device_dy=device_dy,
            data_folder=data_folder,
            save_dir=save_dir,
            save_data=sweep_save_data,
            programs=programs,
            program_configs=program_configs,
        )

        for pr, pr_config in zip(programs, program_configs):
            MeasurementSweep.run_single(
                instr_b1500=instr_b1500,
                monitor_channel=monitor_channel,
                signal_cancel=signal_cancel,
                sweep_metadata=sweep_metadata,
                data_folder=data_folder,
                save_dir=save_dir,
                save_data=sweep_save_data,
                program=pr,
                program_config=pr_config,
            )

            # yields thread for other tasks (so data gets pushed)
            # TODO: proper multithreaded task
            gevent.sleep(0.3)