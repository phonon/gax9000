import os
import logging
import json
import gevent
from controller.sweeps import MeasurementSweep
from controller.util import timestamp, dict_np_array_to_json_array
from controller.util.io import export_hdf5, export_mat

class SweepArray(MeasurementSweep):
    """Implement an array sweep."""
    
    name = "array"
    
    def __repr__(self) -> str:
        return "SweepArray"

    def __str__(self) -> str:
        return self.__repr__()
    
    def default_config_string():
        """Return default `sweep_config` argument in `run` as a dict."""
        return """
            num_rows = 1
            num_cols = 1
            sweep_order = "row"
            programs = []
        """
    
    def run(
        user,
        sweep_config,
        sweep_config_string,
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
        instr_b1500=None,
        instr_cascade=None,
        monitor_channel=None,
        signal_cancel=None,
    ):
        """Run the sweep."""

        # unpack config
        num_rows = sweep_config["num_rows"]
        num_cols = sweep_config["num_cols"]
        sweep_order = sweep_config["sweep_order"]

        # create closure here to simplify passing arguments
        def run_inner(row, col, row_col_str):
            """Run measurement at a (row, col) device in the device array.
            `row_col_str` indicates sweep order:
            - sweep_order = "row": Sweep cols in row, then change row. str is "r0_c0", "r0_c1", ...
            - sweep_order = "col": Sweep rows in col, then change col. str is "c0_r0", "c0_r1", ...
            """
            t_measurement = timestamp()
            save_dir = f"gax_{row_col_str}_{t_measurement}"

            sweep_metadata = MeasurementSweep.save_metadata(
                user=user,
                sweep_name=SweepArray.name,
                sweep_config_string=sweep_config_string,
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
            )

            for pr in programs:
                logging.info(f"[row={row}, col={col}] Running {pr.name}...")
                MeasurementSweep.run_single(
                    instr_b1500=instr_b1500,
                    monitor_channel=monitor_channel,
                    signal_cancel=signal_cancel,
                    sweep_metadata=sweep_metadata,
                    data_folder=data_folder,
                    save_dir=save_dir,
                    save_data=sweep_save_data,
                    program=pr,
                )

                # yields thread for other tasks (so data gets pushed)
                # TODO: proper multithreaded task
                gevent.sleep(0.3)
            
            # yields thread for other tasks
            # TODO: proper multithreaded task
            gevent.sleep(0.3)

        if sweep_order == "row":
            for ny, row in enumerate(range(initial_device_row, initial_device_row + num_rows)):
                for nx, col in enumerate(range(initial_device_col, initial_device_col + num_cols)):
                    run_inner(row, col, row_col_str=f"r{row}_c{col}")
                    # check cancel signal and return if received
                    if signal_cancel is not None and signal_cancel.is_cancelled():
                        logging.info("Measurement cancelled by signal.")
                        return
                    # move chuck by 1 col
                    if nx < (num_cols-1) and instr_cascade is not None:
                        instr_cascade.move_chuck_relative_to_home(x=(nx+1)*device_dx, y=ny*device_dy)
                # move chuck back to col 0, move up by 1 row
                if ny < (num_rows-1) and instr_cascade is not None:
                    instr_cascade.move_chuck_relative_to_home(x=0, y=(ny+1)*device_dy)
        elif sweep_order == "col":
            for nx, col in enumerate(range(initial_device_col, initial_device_col + num_cols)):
                for ny, row in enumerate(range(initial_device_row, initial_device_row + num_rows)):
                    run_inner(row, col, row_col_str=f"c{col}_r{row}")
                    # check cancel signal and return if received
                    if signal_cancel is not None and signal_cancel.is_cancelled():
                        logging.info("Measurement cancelled by signal.")
                        return
                    # move chuck by 1 row
                    if ny < (num_rows-1) and instr_cascade is not None:
                        instr_cascade.move_chuck_relative_to_home(x=nx*device_dx, y=(ny+1)*device_dy)
                # move chuck back to row 0, move by 1 col
                if nx < (num_cols-1) and instr_cascade is not None:
                    instr_cascade.move_chuck_relative_to_home(x=(nx+1)*device_dx, y=0)
        else:
            raise ValueError(f"Invalid sweep_order {sweep_order}, must be 'row' or 'col'")
