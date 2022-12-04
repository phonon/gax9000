import os
import logging
import json
import gevent
from controller.sweeps import MeasurementSweep
from controller.util import timestamp, dict_np_array_to_json_array
from controller.util.io import export_hdf5, export_mat

def create_die_height_offset_interp2d(
    path_die_measurements: str,
):
    """Load die height offset measurements from file and generate heightmap
    using basic linear interpolation. For interpolation methods, see
    https://stackoverflow.com/questions/54432470/how-to-get-a-non-smoothing-2d-spline-interpolation-with-scipy

    Issue with default scipy.interpolate.interp2d is that it relies on
    fitting coefficients, so the resulting curve is smooth. However, this
    does not guarantee the interpolated values will end up going through
    the input points.

    Returns a function `interp2d(x, y): dz` that gives interpolated height
    offset (dz < 0.0) at a given die location (x, y).
    """
    import tomli
    import numpy as np
    from scipy.interpolate import interp2d
    
    with open(path_die_measurements, "rb") as f:
        toml_dict = tomli.load(f)
        
        # fill arrays of points and height offsets
        num_points = len(toml_dict["die_height_offset"])
        x_vals = np.full((num_points,), np.nan)
        y_vals = np.full((num_points,), np.nan)
        dz_vals = np.full((num_points,), np.nan)

        # each measurement is in format like {x: -1.0, y: -2.0, dz: -4}
        for i, x_y_dz in enumerate(toml_dict["die_height_offset"]):
            x, y, dz = x_y_dz.values()
            x_vals[i] = x
            y_vals[i] = y
            dz_vals[i] = dz

        # alternative interpolation method, uses delaunay triangulation
        # and just directly interpolates points. this method ensures heights
        # go through input points
        # die_dz_ct_interp2d = CloughTocher2DInterpolator(
        #     np.concatenate((x_vals[:, None], y_vals[:, None]), axis=1),
        #     dz_vals,
        # )

        # just use scipy.interpolate.interp2d (fits coefficients)
        interp2d_fn = interp2d(x_vals, y_vals, dz_vals, kind="cubic")

        def die_dz_interp2d_func(x, y):
            dz = np.maximum(0.0, interp2d_fn(x, y))
            if np.isscalar(dz):
                return dz
            else:
                return np.squeeze(dz)

        return die_dz_interp2d_func


class SweepMultiDieArray(MeasurementSweep):
    """Implement an array sweep on multiple dies: foreach die
    coordinate, run an array sweep.
    """
    
    name = "multi_die_array"
    
    def __repr__(self) -> str:
        return "SweepMultiDieArray"

    def __str__(self) -> str:
        return self.__repr__()
    
    def default_config():
        """Return default `sweep_config` argument in `run` as a dict."""
        return {
            "dies": [
                [0, 0],
            ],
            "height_compensation_file": None,
            "array": {
                "num_rows": 1,
                "num_cols": 1,
                "sweep_order": "row",
            },
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
        """Run the sweep."""

        # unpack config
        die_coordinates = sweep_config["dies"]
        num_rows = sweep_config["array"]["num_rows"]
        num_cols = sweep_config["array"]["num_cols"]
        sweep_order = sweep_config["array"]["sweep_order"]

        if "height_compensation_file" in sweep_config:
            path_height_compensation = sweep_config["height_compensation_file"]
            die_dz_interp2d = create_die_height_offset_interp2d(path_height_compensation)
            use_height_compensation = True
        else:
            use_height_compensation = False
        
        # create closure here to simplify passing arguments
        def run_inner(
            die_x: int,
            die_y: int,
            row: int,
            col: int,
            row_col_str: str,
        ):
            """Run measurement at a (row, col) device in the device array.
            `row_col_str` indicates sweep order:
            - sweep_order = "row": Sweep cols in row, then change row. str is "r0_c0", "r0_c1", ...
            - sweep_order = "col": Sweep rows in col, then change col. str is "c0_r0", "c0_r1", ...
            """
            t_measurement = timestamp()
            save_dir = os.path.join(f"die_x_{die_x}_y_{die_y}", f"gax_{row_col_str}_{t_measurement}")

            sweep_metadata = MeasurementSweep.save_metadata(
                user=user,
                sweep_name=SweepMultiDieArray.name,
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
                    program_config=pr_config,
                )

                # yields thread for other tasks (so data gets pushed)
                # TODO: proper multithreaded task
                gevent.sleep(0.3)
            
            # yields thread for other tasks
            # TODO: proper multithreaded task
            gevent.sleep(0.3)

        # store current die location
        current_die_x = initial_die_x
        current_die_y = initial_die_y

        for die_coord in die_coordinates:
            die_x, die_y = die_coord
            
            # make sure die coords are integers
            die_x = int(die_x)
            die_y = int(die_y)

            logging.info(f"Moving to die ({die_x}, {die_y})")

            if instr_cascade is not None:
                # move to die location and set home origin
                if current_die_x != die_x or current_die_y != die_y:
                    # move to contact height (stop contacting devices)
                    instr_cascade.move_contacts_up()
                    gevent.sleep(0.5) # ensure small delay

                    # move chuck to target die location using relative coord from current die
                    dx_to_die = (die_x - current_die_x) * die_dx
                    dy_to_die = (die_y - current_die_y) * die_dy
                    logging.info(f"Moving to die ({die_x}, {die_y}) at ({dx_to_die}, {dy_to_die})")
                    instr_cascade.move_chuck_relative_to_home(x=dx_to_die, y=dy_to_die, timeout=20.0)

                    # TODO: do chuck height compensation from baseline

                    # update to new die location and set check home position
                    # (for array measurement) to current die location
                    instr_cascade.set_chuck_home()
                    current_die_x = die_x
                    current_die_y = die_y

                    gevent.sleep(0.5) # ensure small delay

                    # move contacts back down to contact device
                    if use_height_compensation:
                        dz = die_dz_interp2d(die_x, die_y)
                        instr_cascade.move_to_contact_height_with_offset(dz)
                    else:
                        instr_cascade.move_contacts_down()
            
            if sweep_order == "row":
                for ny, row in enumerate(range(initial_device_row, initial_device_row + num_rows)):
                    for nx, col in enumerate(range(initial_device_col, initial_device_col + num_cols)):
                        run_inner(die_x, die_y, row, col, row_col_str=f"r{row}_c{col}")
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
                        run_inner(die_x, die_y, row, col, row_col_str=f"c{col}_r{row}")
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
        
        
