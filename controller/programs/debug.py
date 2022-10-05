import gevent
import time
import numpy as np
from controller.sse import EventChannel
from controller.programs import MeasurementProgram
from controller.util import into_sweep_range, dict_np_array_to_json_array


class ProgramDebug(MeasurementProgram):
    """Implement basic fake debugging program."""

    name = "debug"
    
    def default_config():
        """Return default `run` arguments config as a dict."""
        return {
            "v_gs": [0, 1, 2, 3, 4, 5, 6, 7],
        }
    
    def run(
        v_gs=[0, 1, 2, 3, 4, 5, 6, 7],
        v_ds=[0.05, 0.5, 1.0, 2.0, 4.0, 7.0, 10.0],
        **kwargs
    ) -> dict:
        """Run the program."""
        print("RUNNING DEBUG PROGRAM")

        # simulate running
        gevent.sleep(2)
        
        # convert v_gs and v_ds into numpy arrays
        v_gs_sweep = into_sweep_range(v_gs)
        v_ds_sweep = into_sweep_range(v_ds)

        # get num points/bias points
        num_bias = len(v_ds_sweep)
        num_sweeps = 2
        num_points = len(v_gs_sweep)

        v_gs_arr = np.array(v_gs_sweep, dtype=np.float64)

        data_shape = (num_bias, num_sweeps, num_points)
        v_ds_out = np.full(data_shape, np.nan)
        v_gs_out = np.full(data_shape, np.nan)
        i_d_out = np.full(data_shape, np.nan)
        i_s_out = np.full(data_shape, np.nan)
        i_g_out = np.full(data_shape, np.nan)
        
        for b in range(num_bias):
            for d in range(num_sweeps):
                v_ds_out[b, d, :] = v_ds_sweep[b]
                v_gs_out[b, d, :] = v_gs_arr
                i_d_out[b, d, :] = 1e-6 + 1e-6 * (np.abs(v_gs_arr) + float(d)*0.25) * float(b+1)
                i_s_out[b, d, :] = -1e-6 -1e-6 * (np.abs(v_gs_arr) + float(d)*0.25) * float(b+1)
                i_g_out[b, d, :] = 1e-9 + 1e-9 * np.abs(v_gs_arr) * float(b+1)

        return {
            "v_ds": v_ds_out,
            "v_gs": v_gs_out,
            "i_d": i_d_out,
            "i_s": i_s_out,
            "i_g": i_g_out,
        }


class ProgramDebugMultistep(MeasurementProgram):
    """Implement fake debugging program.
    This sweeps each `v_ds` value and inserts dummy measurement delay for
    each `v_ds` step. Tests continuous data stream output from measurement.
    """

    name = "debug_multistep"
    
    def default_config():
        """Return default `run` arguments config as a dict."""
        return {
            "v_gs": [0, 1, 2, 3, 4, 5, 6, 7],
        }
    
    def run(
        monitor_channel: EventChannel = None,
        sweep_metadata: dict = {},
        v_gs=[0, 1, 2, 3, 4, 5, 6, 7],
        v_ds=[0.5, 1.0, 4.0],
        delay=4,
        **kwargs
    ) -> dict:
        """Run the program."""
        
        print(f"[ProgramDebugMultistep] START")
        
        # convert v_gs and v_ds into numpy arrays
        v_gs_sweep = into_sweep_range(v_gs)
        v_ds_sweep = into_sweep_range(v_ds)

        # get num points/bias points
        num_bias = len(v_ds_sweep)
        num_sweeps = 2
        num_points = len(v_gs_sweep)

        v_gs_arr = np.array(v_gs_sweep, dtype=np.float64)

        data_shape = (num_bias, num_sweeps, num_points)
        v_ds_out = np.full(data_shape, np.nan)
        v_gs_out = np.full(data_shape, np.nan)
        i_d_out = np.full(data_shape, np.nan)
        i_s_out = np.full(data_shape, np.nan)
        i_g_out = np.full(data_shape, np.nan)
        
        for b in range(num_bias):

            print(f"[ProgramDebugMultistep] STEP {b+1}/{num_bias} (v_ds = {v_ds_sweep[b]} V)")

            # simulate running
            gevent.sleep(delay)

            for d in range(num_sweeps):
                v_ds_out[b, d, :] = v_ds_sweep[b]
                v_gs_out[b, d, :] = v_gs_arr
                i_d_out[b, d, :] = 1e-6 + 1e-6 * (np.abs(v_gs_arr) + float(d)*0.25) * float(b+1)
                i_s_out[b, d, :] = -1e-6 -1e-6 * (np.abs(v_gs_arr) + float(d)*0.25) * float(b+1)
                i_g_out[b, d, :] = 1e-9 + 1e-9 * np.abs(v_gs_arr) * float(b+1)
            
            def task_update_program_status():
                """Update program status."""
                data = {
                    "v_ds": v_ds_out,
                    "v_gs": v_gs_out,
                    "i_d": i_d_out,
                    "i_s": i_s_out,
                    "i_g": i_g_out,
                }
                monitor_channel.publish({
                    "metadata": {
                        "program": "debug_multistep",
                        "config": sweep_metadata,
                        "step": b,
                        "step_total": num_bias,
                    },
                    "data": dict_np_array_to_json_array(data), # converts np ndarrays to regular lists
                })
            
            if monitor_channel is not None and b < num_bias-1: # don't publish last step
                gevent.spawn(task_update_program_status)
            
        print(f"[ProgramDebugMultistep] FINISHED")

        return {
            "v_ds": v_ds_out,
            "v_gs": v_gs_out,
            "i_d": i_d_out,
            "i_s": i_s_out,
            "i_g": i_g_out,
        }