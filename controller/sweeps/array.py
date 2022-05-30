import os
import logging
from controller.sweeps import MeasurementSweep
from controller.util import timestamp
from controller.util.io import export_hdf5, export_mat

class SweepArray(MeasurementSweep):
    """Implement an array sweep."""
    
    name = "array"
    
    def __repr__(self) -> str:
        return "SweepArray"

    def __str__(self) -> str:
        return self.__repr__()
    
    def default_config():
        """Return default `sweep_config` argument in `run` as a dict."""
        return {
            "num_rows": 1,
            "num_cols": 1,
            "sweep_order": "row",
            "programs": [],
        }
    
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
            logging.info(f"[row={row}, col={col}] Running {program.name}...")
            result = program.run(**program_config)

            if sweep_save_data and os.path.exists(data_folder):
                t_measurement = timestamp()
                save_dir = f"gax_{row_col_str}_{program.name}_{t_measurement}"
                path_dir = os.path.join(data_folder, save_dir)
                os.makedirs(path_dir, exist_ok=True)

                path_meta = os.path.join(path_dir, "meta.json")
                path_result_h5 = os.path.join(path_dir, f"{program.name}.h5")
                path_result_mat = os.path.join(path_dir, f"{program.name}.mat")

                MeasurementSweep.export_metadata(
                    path=path_meta,
                    user=user,
                    sweep=SweepArray.name,
                    sweep_config=sweep_config,
                    die_x=current_die_x,
                    die_y=current_die_y,
                    device_row=row,
                    device_col=col,
                    device_dx=device_x,
                    device_dy=device_y,
                    data_folder=data_folder,
                    program_name=program.name,
                    program_config=program_config,
                )
                export_hdf5(path_result_h5, result)
                export_mat(path_result_mat, result)

        if sweep_order == "row":
            for row in range(device_row, device_row + num_rows):
                for col in range(device_col, device_col + num_cols):
                    run_inner(row, col, row_col_str=f"r{row}_c{col}")
        elif sweep_order == "col":
            for col in range(device_col, device_col + num_cols):
                for row in range(device_row, device_row + num_rows):
                    run_inner(row, col, row_col_str=f"c{col}_r{row}")
        else:
            raise ValueError(f"Invalid sweep_order {sweep_order}, must be 'row' or 'col'")
        
        
