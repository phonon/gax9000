import os
from controller.sweeps import MeasurementSweep
from controller.util import timestamp
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
        device_x,
        device_y,
        device_row,
        device_col,
        data_folder,
        program,
        program_config,
    ):
        """Run the sweep."""
        result = program.run(**program_config)

        if sweep_save_data and os.path.exists(data_folder):
            t_measurement = timestamp()
            save_dir = f"gax_r{device_row}_c{device_col}_{program.name}_{t_measurement}"
            path_dir = os.path.join(data_folder, save_dir)
            os.makedirs(path_dir, exist_ok=True)

            path_meta = os.path.join(path_dir, "meta.json")
            path_result_h5 = os.path.join(path_dir, f"{program.name}.h5")
            path_result_mat = os.path.join(path_dir, f"{program.name}.mat")

            MeasurementSweep.export_metadata(
                path=path_meta,
                user=user,
                sweep=SweepSingle.name,
                sweep_config=sweep_config,
                die_x=current_die_x,
                die_y=current_die_y,
                device_row=device_row,
                device_col=device_col,
                device_dx=device_x,
                device_dy=device_y,
                data_folder=data_folder,
                program_name=program.name,
                program_config=program_config,
            )
            export_hdf5(path_result_h5, result)
            export_mat(path_result_mat, result)
