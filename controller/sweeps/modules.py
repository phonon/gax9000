"""
Sweep by modules.
"""
import logging
import gevent
from controller.sweeps import MeasurementSweep
from controller.util import timestamp


def load_modules_from_toml(modules_file: str) -> dict:
    """Load modules dictionary from TOML file."""
    import tomli
    with open(modules_file, "rb") as f:
        toml = tomli.load(f)
    return toml["modules"]

def load_sweep_from_toml(sweep_file: str) -> list:
    """Load modules sweep list from TOML file."""
    import tomli
    with open(sweep_file, "rb") as f:
        toml = tomli.load(f)
    return toml["sweep"]

class SweepModules(MeasurementSweep):
    """Implement a modules sweep."""
    
    name = "modules"
    
    def __repr__(self) -> str:
        return "SweepModules"

    def __str__(self) -> str:
        return self.__repr__()
    
    def default_config_string():
        return """
            # modules_file = "modules.toml" # uncomment to use modules file .toml
            # sweep_file = "sweeps.toml"    # uncomment to use sweep file .toml

            # or define local modules here (same format as modules file)
            [modules]
            module1 = { name = "module1", x = 0, y = 0 }
            module2 = { name = "module2", x = 50, y = 0 }
            module3 = { name = "module3", x = 100, y = 0 }

            [sweep]
            modules = ["module1", "module2", "module3"]
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
        if sweep_config.get("modules_file") is not None:
            modules = load_modules_from_toml(sweep_config["modules_file"])
        else:
            modules = sweep_config["modules"]
        
        if sweep_config.get("sweep_file") is not None:
            sweep = load_sweep_from_toml(sweep_config["sweep_file"])["modules"]
        else:
            sweep = sweep_config["sweep"]["modules"]
        
        ### DEBUG
        # print(f"modules: {modules}, sweep: {sweep}")

        # create closure here to simplify passing arguments
        def run_inner(
            module_str: str,
        ):
            """Run measurement at a named module device.
            - `module_str`: module name (mainly as metadata).
            """
            t_measurement = timestamp()
            save_dir = f"gax_{module_str}_{t_measurement}"

            sweep_metadata = MeasurementSweep.save_metadata(
                user=user,
                sweep_name=SweepModules.name,
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
                logging.info(f"[module={module_str}] Running {pr.name}...")
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

        for module_name in sweep:
            module = modules[module_name]

            # local (x, y) coordinates relative to die home
            x_module = module["x"]
            y_module = module["y"]
            
            if instr_cascade is not None:
                instr_cascade.move_chuck_relative_to_home(x=x_module, y=y_module)
            
            run_inner(module_name)

            # check cancel signal and return if received
            if signal_cancel is not None and signal_cancel.is_cancelled():
                logging.info("Measurement cancelled by signal.")
                return
