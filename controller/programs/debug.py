import gevent
import logging
import time
import numpy as np
from controller.sse import EventChannel
from controller.programs import MeasurementProgram, MeasurementResult
from controller.util import into_sweep_range, dict_np_array_to_json_array, exp_moving_avg_with_init


def start_measurement() -> float:
    """Simulate starting measurement, returns starting timestamp"""
    return time.time()

def finish_measurement(t_start: float, t_measure: float) -> float:
    """Simulate blocking wait for measurement results. This is equivalent to
    trying to read data from GPIB query in pyvisa.
    This will simulate halting with a full python time.sleep until the
    measurement has "completed".
    Returns timestamp when measurement "completed".
    """
    dt_remaining = t_measure - (time.time() - t_start)
    if dt_remaining > 0:
        time.sleep(dt_remaining)
    return time.time()


class ProgramDebug(MeasurementProgram):
    """Implement basic fake debugging program."""

    name = "debug"
    
    def default_config_string() -> str:
        """Return default `run` arguments config as a toml format string."""
        return """
            v_gs = [0, 1, 2, 3, 4, 5, 6, 7]
        """
    
    def run(
        v_gs=[0, 1, 2, 3, 4, 5, 6, 7],
        v_ds=[0.05, 0.5, 1.0, 2.0, 4.0, 7.0, 10.0],
        **kwargs
    ) -> dict:
        """Run the program."""
        logging.info("RUNNING DEBUG PROGRAM")

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

        return MeasurementResult(
            cancelled=False,
            data={
                "v_ds": v_ds_out,
                "v_gs": v_gs_out,
                "i_d": i_d_out,
                "i_s": i_s_out,
                "i_g": i_g_out,
            },
        )


class ProgramDebugMultistep(MeasurementProgram):
    """Implement fake debugging program.
    This sweeps each `v_ds` value and inserts dummy measurement delay for
    each `v_ds` step. Tests continuous data stream output from measurement.
    """

    name = "debug_multistep"
    
    def default_config_string() -> str:
        """Return default `run` arguments config as a dict."""
        return """
            v_ds = [0.1, 1.0, 2.0]
            v_gs = [0, 1, 2, 3, 4, 5, 6, 7]
        """
    
    def run(
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        v_gs=[0, 1, 2, 3, 4, 5, 6, 7],
        v_ds=[0.5, 1.0, 4.0],
        delay=4,
        yield_during_measurement=True,
        **kwargs
    ) -> dict:
        """Run the program."""
        
        logging.info(f"[ProgramDebugMultistep] START")

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

        # sweep state
        t_run_avg = None  # avg program step time
        cancelled = False # flag for program cancelled before done

        for b in range(num_bias):

            logging.info(f"[ProgramDebugMultistep] STEP {b+1}/{num_bias} (v_ds = {v_ds_sweep[b]} V)")
            
            # simulate running measurement and a blocking read query
            t_start = start_measurement()

            # here we yield the green thread during measurement to let other tasks run
            # we estimate the avg time remaining for the measurement, with some margin
            # so we don't oversleep.
            if yield_during_measurement and t_run_avg is not None and t_run_avg > 0:
                t_sleep = 0.9 * t_run_avg
                logging.info(f"[ProgramDebugMultistep] SLEEPING: gevent.sleep({t_sleep:.3f})")
                gevent.sleep(t_sleep)

            t_finish = finish_measurement(t_start, delay) # blocks all threads until delay passes from t_start

            # update avg measurement time for accurate gevent sleep
            t_run = t_finish - t_start
            t_run_avg = max(0, exp_moving_avg_with_init(t_run_avg, t_run, alpha=0.2, init_alpha=0.9))
            
            logging.info(f"[ProgramDebugMultistep] MEASUREMENT FINISHED: t={t_run:.3f}s, t_avg={t_run_avg:.3f}s")

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
            
            if signal_cancel is not None:
                logging.info(f"[ProgramDebugMultistep] CANCEL STATUS: {signal_cancel}")
                if signal_cancel.is_cancelled():
                    logging.info(f"[ProgramDebugMultistep] CANCELLING PROGRAM")
                    cancelled = True
                    break
            
        logging.info(f"[ProgramDebugMultistep] FINISHED")

        return MeasurementResult(
            cancelled=cancelled,
            data={
                "v_ds": v_ds_out,
                "v_gs": v_gs_out,
                "i_d": i_d_out,
                "i_s": i_s_out,
                "i_g": i_g_out,
            },
        )