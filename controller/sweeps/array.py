from controller.sweeps import MeasurementSweep

class SweepArray(MeasurementSweep):
    """Implement an array sweep."""
    
    name = "array"
    
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
        program.run(**program_config)

        if sweep_save_data:
            print("SAVING SWEEP DATA")