from controller.sweeps import MeasurementSweep

class SweepSingle(MeasurementSweep):
    """Implement a single device sweep."""
    
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