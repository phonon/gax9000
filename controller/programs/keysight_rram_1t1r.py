"""
Implement 1T1R rram measurement.
                 Vg
                __|__
        Vd  ____|   |____xxxxxx____ Vs
                 FET      RRAM
1T1R RRAM structure is a FET and RRAM in series. The FET serves
two purposes:
    1.  Enforces a compliance current for setting the RRAM to
        allow a more stable voltage-controlled resistance set.
    2.  Limits current for unselected cells in RRAM array.
The structure requires a three terminal measurement:
    - Vg: transistor gate voltage sets max fet current
    - Vd: drain voltage bias
    - Vs: source voltage bias
The measurement has three sweep parts: form, set, reset

        Vform
         ___           Vset             Vset
        |   |           ___             ___             
        |   |          |   |           |   |            
________|   |___     __|   |___     ___|   |___ ...
                |   |          |   |           
                |___|          |___|           
                Vreset         Vreset          

This measurement allows running sequences of form/reset/set/reset/...
sweeps. The sweep sequence input is a string of characters:
    "fsrsrsr..."
- "f": form sweep (forward/rev staircase to Vform)
- "s": set sweep (forward/rev staircase to Vset)
- "r": reset sweep (forward/rev staircase to Vreset)

Aim for ~100 uA current into the RRAM cell to form.
Top vs bottom FET RRAM config. Example configuration and sweeps
shown below (for FORMING/SET sweep positive voltage on top,
RESET use negative voltage on top):

                VS = [0, 1] V            TE = [0, 1] V
                _                        _
                |                        |
            |---+                        X
     Vg ---o|      (PMOS)                X  RRAM
    = -1 V  |---+                        X  (TE)
                |                        |
                |                        |
                X                        +---|
                X   RRAM         (NMOS)      |---- Vg
                X   (BE)                 +---|    = 1 V
                |                        |
                v                        v
                BE = 0 V                 VS = 0 V
"""
import traceback
import os
import numpy as np
import gevent
import pyvisa
import logging
from time import time
from tabulate import tabulate
from controller.programs import MeasurementProgram, MeasurementResult, SweepType
from controller.sse import EventChannel
from controller.util import into_sweep_range, parse_keysight_str_values, iter_chunks, map_smu_to_slot, dict_np_array_to_json_array, exp_moving_avg_with_init
from controller.util.io import export_hdf5, export_mat


class RramSweepConfig():
    """
    Common RRAM sweep bias configuration for all measurement programs.
    Contains:
    - v_sub: substrate voltage (constant)
    - v_s: source voltage (constant)
    - v_g: gate voltage (constant)
    - v_d: drain voltage (sweep)
    """
    def __init__(
        self,
        name,
        v_sub,
        v_s,
        v_g,
        v_d_sweep,
    ):
        self.name = name
        self.v_sub = v_sub
        self.v_s = v_s
        self.v_g = v_g
        self.v_d_sweep = v_d_sweep
        self.num_points = len(v_d_sweep)

    def __repr__(self) -> str:
        return f"RramSweepConfig(name='{self.name}', v_sub={self.v_sub}, v_s={self.v_s}, v_g={self.v_g}, v_d_sweep={self.v_d_sweep})"


def sweep_sequence_data_block(
    num_sequences,
    num_points_max,
    num_directions=2, # forward/reverse
) -> dict:
    """
    Standard rram 1T1R measurement sequence sweep data block.
    Shared for all measurement programs.
    Format is (nsequences, ndirections, npoints_max).
    - nsequences: number of measurement sequences, e.g. a form/reset/set sequence:
        "frsrsr" -> 6 sequences
    - ndirections: number of forward/reverse sweep directions = 2
    - npoints_max: maximum number of points in a sweep sequence, e.g. if we have
        v_d sequences:
        v_d_form = [0, 1, 2, 3, 4]   -> npoints_form = 5
        v_d_set = [0, 1, 2]          -> npoints_set = 3
        v_d_reset = [0, -1, -2, -3]  -> npoints_reset = 4
        npoints_max = max(npoints_form, npoints_set, npoints_reset) = 5

    Data block contains groups of data with np.nan padding to match npoints_max:
        v_g = 
        FORM  [0,   1,   2,   3,   4]
        RESET [0,  -1,  -2,  -3, nan]
        SET   [0,   1,   2, nan, nan]
        RESET [0,  -1,  -2,  -3, nan]
        SET   [0,   1,   2, nan, nan]
        RESET [0,  -1,  -2,  -3, nan]
    ...
    """
    data_shape = (num_sequences, num_directions, num_points_max)

    return {
        "v_s": np.full(data_shape, np.nan),
        "v_d": np.full(data_shape, np.nan),
        "v_g": np.full(data_shape, np.nan),
        "i_s": np.full(data_shape, np.nan),
        "i_d": np.full(data_shape, np.nan),
        "i_g": np.full(data_shape, np.nan),
        "time_i_s": np.full(data_shape, np.nan), # timestamps
        "time_i_d": np.full(data_shape, np.nan),
        "time_i_g": np.full(data_shape, np.nan),
    }


def calculate_derived_measurement_values(
    data_measurement,
) -> dict:
    """
    Add any standard derived measurement values to the post-measured data.
    Things like resistance = v/i.
    """
    # absolute value of currents
    data_measurement["i_d_abs"] = np.abs(data_measurement["i_d"])
    data_measurement["i_s_abs"] = np.abs(data_measurement["i_s"])
    data_measurement["i_g_abs"] = np.abs(data_measurement["i_g"])
    # add channel resistance = v_d / i_d
    data_measurement["res"] = np.abs(data_measurement["v_d"] / data_measurement["i_d"])

    return data_measurement


def _query_error(instr_b1500, stop_on_error=True):
    """Internal shared function for querying error status from Keysight B1500."""
    res = instr_b1500.query("ERRX?")
    if res[0:2] != "+0":
        logging.error(f"{res}")
        if stop_on_error:
            raise RuntimeError(res)

def measurement_keysight_b1500_setup(
    instr_b1500,
    query_error,
    probe_wl: int,
    probe_sl: int,
    probe_bl: int,
    probe_sub: int,
    id_compliance: float,
    ig_compliance: float,
    pow_compliance: float,
):
    """Standard shared setup for 1T1R RRAM measurements.
    """

    # enable channels: CN (pg 4-62)
    instr_b1500.write(f"CN {probe_sub},{probe_wl},{probe_bl},{probe_sl}")
    query_error(instr_b1500)

    instr_b1500.write("FMT 1,1") # clear data buffer and set format (4-24, 4-25)
    instr_b1500.write("TSC 1")   # enables timestamp output
    instr_b1500.write("FL 0")    # set filter off
    query_error(instr_b1500)

    # instr_b1500.write("AV 10,1") # sets ADC number of samples for 1 data
    # query_error(instr_b1500)

    # select type of A/D converter (4-33, pg 353):
    #   ADD channel,type
    ADC_TYPE_HISPEED = 0
    ADC_TYPE_HIRES = 1
    ADC_TYPE_PULSE = 2
    adc_type = ADC_TYPE_HISPEED
    instr_b1500.write(f"AAD {probe_bl},{adc_type}")
    instr_b1500.write(f"AAD {probe_sl},{adc_type}")
    instr_b1500.write(f"AAD {probe_wl},{adc_type}")
    instr_b1500.write(f"AAD {probe_sub},{adc_type}")
    query_error(instr_b1500)


    # Sets up high speed adc (4-38, pg 358)""
    #   AIT type,mode,N
    # type: ADC type of the A/D converter. Integer 0, 1, or 2
    #       0: high-speed ADC
    #       1: high-resolution ADC
    #       2: high-speed ADC for pulsed measurement
    # mode: ADC operation mode
    #       0: auto-mode, initial setting
    #       1: manual mode
    #       2: power line cycle (PLC) mode
    #       3: measurement time mode, not available for the high-res adc
    # N: coefficient used to define the integration time or the number of
    # averaging samples, integer expression, for mode = 0, 1 and 2. Or the
    # actual measurement time, numeric expression, for mode = 3... see table
    # 4-21 on page 4-39
    ADC_HISPEED_MODE_AUTO = 0
    ADC_HISPEED_MODE_MANUAL = 1
    ADC_HISPEED_MODE_POWER_LINE_CYCLE = 2
    ADC_HISPEED_MODE_MEASUREMENT_TIME = 3

    adc_mode = ADC_HISPEED_MODE_AUTO
    adc_sampling_coeff = 30

    instr_b1500.write(f"AIT {adc_type},{adc_mode},{adc_sampling_coeff}")
    query_error(instr_b1500)

    # zero voltage to probes, DV (pg 4-78) cmd sets DC voltage on channels:
    #   DV {probe},{vrange},{v},{icompliance}
    instr_b1500.write(f"DV {probe_wl},0,0,{ig_compliance}")
    instr_b1500.write(f"DV {probe_sub},0,0,{id_compliance}")
    instr_b1500.write(f"DV {probe_bl},0,0,{id_compliance}")
    instr_b1500.write(f"DV {probe_sl},0,0,{id_compliance}")
    query_error(instr_b1500)

    # set measurement mode to multi-channel staircase sweep (MODE = 16) (4-151, pg 471):
    #   MM mode,ch0,ch1,ch2,...
    mm_mode = 16
    instr_b1500.write(f"MM {mm_mode},{probe_bl},{probe_sl},{probe_wl}");
    query_error(instr_b1500)

    # set probe current measurement mode (4-62, pg 382):
    #   CMM ch,mode
    CMM_MODE_COMPLIANCE = 0
    CMM_MODE_CURRENT = 1
    CMM_MODE_VOLTAGE = 2
    CMM_MODE_FORCE = 3
    CMM_MODE_SYNC = 4
    cmm_mode = CMM_MODE_CURRENT
    instr_b1500.write(f"CMM {probe_bl},{cmm_mode}")
    instr_b1500.write(f"CMM {probe_sl},{cmm_mode}")
    instr_b1500.write(f"CMM {probe_wl},{cmm_mode}")
    query_error(instr_b1500)

    # set auto-ranging (4-183 pg 503, page 339 for modes)
    RANGE_MODE_AUTO = 0      # auto
    RANGE_MODE_10PA = 9      # 10 pA limited auto
    RANGE_MODE_100PA = 10    # 100 pA limited auto
    RANGE_MODE_1NA = 11      # 1 nA limited auto
    RANGE_MODE_10NA = 12     # 10 nA limited auto
    RANGE_MODE_100NA = 13    # 100 nA limited auto
    RANGE_MODE_1UA = 14      # 1 uA limited auto
    RANGE_MODE_1MA = 17      # 1 mA limited auto
    range_mode = RANGE_MODE_1NA
    instr_b1500.write(f"RI {probe_sl},{range_mode}")
    instr_b1500.write(f"RI {probe_bl},{range_mode}")
    instr_b1500.write(f"RI {probe_wl},{range_mode}")
    query_error(instr_b1500)

    # set hold time, delay time, and step delay time for the staircase sweep or
    # multi-channel sweep measurement (pg 4-246, pg 566)
    #   WT hold,delay[,Sdelay[,Tdelay[,Mdelay]]]
    # - hold: Hold time (in seconds) that is the wait time after starting the sweep
    #       measurement and before starting the delay time for the first step.
    #       0 to 655.35, with 10 ms resolution. Numeric expression.
    # - delay: Delay time (in seconds) that is the wait time after starting to
    #       force a step output and before starting a step measurement.
    #       0 to 65.535, with 0.1 ms resolution. Numeric expression.
    # - Sdelay : Step delay time (in seconds) that is the wait time after starting a step
    #       measurement and before starting to force the next step output value.
    #       If this parameter is not set, Sdelay will be 0.
    #       If Sdelay is shorter than the measurement time, the B1500 waits until
    #       the measurement completes, then forces the next step output.
    #
    # | hold | force | delay | Sdelay      | force | delay | Sdelay      |
    #                        | measure |                   | measure |
    #        |<----- repeat -------------->|
    #
    wt_hold = 0.010  # 10 ms
    wt_delay = 0.010 # 10 ms, seems OK. if this is not 0, then it seems like first measurement is much lower than the others
    wt_sdelay = 0    # step delay
    instr_b1500.write(f"WT {wt_hold},{wt_delay},{wt_sdelay}")
    query_error(instr_b1500)

    # enable/disable automatic abort function WM (4-234, pg 554)
    #   The WM command enables or disables the automatic abort function for the
    #   staircase sweep sources and the pulsed sweep source. The automatic abort
    #   function stops the measurement when one of the following conditions
    #   occurs:
    #   - compliance on the measurement channel
    #   - compliance on the non-measurement channel
    #   - overflow on the AD converter
    #   - oscillation on any channel
    #   This command also sets the post measurement condition for the sweep
    #   sources. After the measurement is normally cmopleted, the staircase sweep
    #   sources force the value specified by the 'post' parameter, and the pulsed
    #   sweep source forces the pulse base value
    #
    #   WM abort[,post]
    # Parameters:
    # - abort : Automatic abort function.
    #       1: Disables the function. Initial setting.
    #       2: Enables the function.
    # - post : Source output value after the measurement is normally completed.
    #       1: Start value. Initial setting.
    #       2: Stop value.
    #       If this parameter is not set, the sweep sources force the start value.
    #
    # Output Data : The B1500 returns the data measured before an abort
    # condition is detected. Dummy data 199.999E+99 will be returned for the
    # data after abort
    WM_ABORT_DISABLE = 1
    WM_ABORT_ENABLE = 2
    WM_POST_START_VALUE = 1
    WM_POST_STOP_VALUE = 2
    instr_b1500.write(f"WM {WM_ABORT_DISABLE},{WM_POST_STOP_VALUE}")
    query_error(instr_b1500)

    # timestamp reset
    instr_b1500.write(f"TSR")
    query_error(instr_b1500)


def run_rram_1t1r_sweeps(
    program_name: str,
    instr_b1500,
    monitor_channel: EventChannel,
    signal_cancel,
    sweep_metadata,
    query_error,
    probe_wl: int,
    probe_sl: int,
    probe_bl: int,
    probe_sub: int,
    id_compliance: float,           # drain current compliance
    ig_compliance: float,           # gate current compliance
    yield_during_measurement: bool, # yield greenlet thread during measurement
    bias_configs: list,
    data_measurement: dict,
):
    """Common core inner loop to run list of rram 1T1R bitline bias config
    sweeps in keysight b1500. This is used by all rram 1T1R measurement
    programs.
    """
    # derived parameters
    num_sequences = len(bias_configs)

    # internal sweep state
    t_run_avg = None  # avg program step time
    cancelled = False # flag for program cancelled before done

    for step, sweep in enumerate(bias_configs):
        # unpack sweep bias config
        v_sub = sweep.v_sub
        v_s = sweep.v_s
        v_g = sweep.v_g
        v_d_sweep = sweep.v_d_sweep
        num_points = sweep.num_points
        
        # print(f"v_s = {v_s}")
        # print(f"v_g = {v_g}")
        # print(f"v_sweep = {v_sweep}")
        # print(f"num_points = {num_points}")

        print(f"============================================================")
        print(f"Measuring step {step}: {sweep.name}")
        print(f"v_s = {v_s}")
        print(f"v_g = {v_g}")
        print(f"v_d = {v_d_sweep[0]} -> {v_d_sweep[-1]}")
        print(f"------------------------------------------------------------")
        
        # write voltage staircase waveform
        wv_range_mode = 0 # AUTO
        wv_cmd = SweepType.FORWARD_REVERSE.b1500_wv_sweep_command(
            ch=probe_bl,
            range=wv_range_mode,
            start=v_d_sweep[0],
            stop=v_d_sweep[-1],
            steps=num_points,
            icomp=id_compliance,
            pcomp=None, # ignore for now
        )
        # print(wv_cmd)
        instr_b1500.write(wv_cmd)
        query_error(instr_b1500)
        
        # write bulk bias
        instr_b1500.write(f"DV {probe_sub},0,{v_sub},{id_compliance}")
        query_error(instr_b1500)
        
        # write source bias
        instr_b1500.write(f"DV {probe_sl},0,{v_s},{id_compliance}")
        query_error(instr_b1500)

        # write gate bias
        instr_b1500.write(f"DV {probe_wl},0,{v_g},{ig_compliance}")
        query_error(instr_b1500)

        # execute and wait for data response
        instr_b1500.write("XE")
        
        # starting time for step
        t_start = time()

        # yield green thread during measurement to let other tasks run
        if yield_during_measurement and t_run_avg is not None and t_run_avg > 0:
            t_sleep = 0.9 * t_run_avg
            logging.info(f"[ProgramKeysightRram1T1R] SLEEPING: gevent.sleep({t_sleep:.3f})")
            gevent.sleep(t_sleep)

        # set timeout (milliseconds)
        instr_b1500.timeout = 60 * 1000
        _opc = instr_b1500.query("*OPC?")
        instr_b1500.timeout = 10 * 1000
        query_error(instr_b1500)

        # update avg measurement time for accurate gevent sleep
        t_finish = time()
        t_run = t_finish - t_start
        t_run_avg = max(0, exp_moving_avg_with_init(t_run_avg, t_run, alpha=0.2, init_alpha=0.9))

        # zero probes after measurement
        instr_b1500.write(f"DV {probe_wl},0,0,{ig_compliance}")
        instr_b1500.write(f"DV {probe_sub},0,0,{id_compliance}")
        instr_b1500.write(f"DV {probe_bl},0,0,{id_compliance}")
        instr_b1500.write(f"DV {probe_sl},0,0,{id_compliance}")
        query_error(instr_b1500)
        
        # number of bytes in output data buffer
        nbytes = int(instr_b1500.query("NUB?"))
        print(f"nbytes={nbytes}")
        buf = instr_b1500.read()
        # print(buf)

        # parse vals strings into numbers
        vals = buf.strip().split(",")
        vals = parse_keysight_str_values(vals)

        # values chunked for each measurement point:
        #   [ [vd0, id0, ig0] , [vgs1, id1, ig1], ... ]
        val_chunks = [ x for x in iter_chunks(vals, 7) ]

        # split val chunks into forward/reverse sweep components:
        sweep_chunks = [val_chunks[0:num_points], val_chunks[num_points:]]

        # values to print out to console for display
        val_table = []

        for s, sweep_vals in enumerate(sweep_chunks):
            for i, vals_chunk in enumerate(sweep_vals):
                val_table.append([v_g, vals_chunk[6], vals_chunk[1], vals_chunk[3], vals_chunk[5]])
                
                data_measurement["v_s"][step, s, i] = v_s
                data_measurement["v_g"][step, s, i] = v_g
                data_measurement["v_d"][step, s, i] = vals_chunk[6]
                data_measurement["i_d"][step, s, i] = vals_chunk[1]
                data_measurement["i_s"][step, s, i] = vals_chunk[3]
                data_measurement["i_g"][step, s, i] = vals_chunk[5]
                # timestamps
                data_measurement["time_i_d"][step, s, i] = vals_chunk[0]
                data_measurement["time_i_s"][step, s, i] = vals_chunk[2]
                data_measurement["time_i_g"][step, s, i] = vals_chunk[4]
        
        print(tabulate(val_table, headers=["v_g [V]", "v_d [V]", "i_d [A]", "i_s [A]", "i_g [A]"]))

        print("============================================================")
        
        if monitor_channel is not None and step < num_sequences-1: # don't publish last step
            def task_update_program_status():
                """Update program status."""
                data_cleaned = calculate_derived_measurement_values(data_measurement)
                data_cleaned = dict_np_array_to_json_array(data_cleaned) # converts np ndarrays to regular lists and replace nan

                monitor_channel.publish({
                    "metadata": {
                        "program": program_name,
                        "config": sweep_metadata,
                        "step": step,
                        "step_total": num_sequences,
                    },
                    "data": data_cleaned, 
                })
            gevent.spawn(task_update_program_status)
        
        if signal_cancel is not None and signal_cancel.is_cancelled():
            logging.info(f"[ProgramKeysightRram1T1R] CANCELLING PROGRAM")
            cancelled = True
            break
    
    # add derived measurement data
    # e.g. channel resistance
    data_measurement = calculate_derived_measurement_values(data_measurement)

    return data_measurement, cancelled


class ProgramKeysightRram1T1R(MeasurementProgram):
    """Implement most basic 1T1R single-bit form/reset/set sweeps.  

            Vform
             ___           Vset             Vset
            |   |           ___             ___             
            |   |          |   |           |   |            
    ________|   |___     __|   |___     ___|   |___ ...
                    |   |          |   |           
                    |___|          |___|           
                    Vreset         Vreset          
    
    This measurement allows running sequences of form/reset/set/reset/...
    sweeps. The sweep sequence input is a string of characters:
        "fsrsrsr..."
    - "f": form sweep (forward/rev staircase to Vform)
    - "s": set sweep (forward/rev staircase to Vset)
    - "r": reset sweep (forward/rev staircase to Vreset)

    This only allow 3 built-in f/s/r values. For very basic testing.
    """
    name = "keysight_rram_1t1r"

    @staticmethod
    def parse_sweep_sequence(
        sequence,
        v_sub,
        v_s_form,
        v_g_form,
        v_d_form_range,
        v_s_set,
        v_g_set,
        v_d_set_range,
        v_s_reset,
        v_g_reset,
        v_d_reset_range,
    ):
        """Helper function to parse a form/reset/set code into a
        sequence of sweep bias configs. Made this separate function
        so that its easier to debug the sweep config parsing in external
        test functions.
        """
        bias_configs = []
        
        for i in range(len(sequence)):
            pattern = sequence[i]
            if pattern == "f": # form
                bias_configs.append(RramSweepConfig(name="form", v_sub=v_sub, v_s=v_s_form, v_g=v_g_form, v_d_sweep=v_d_form_range))
            elif pattern == "s": # set
                bias_configs.append(RramSweepConfig(name="set", v_sub=v_sub, v_s=v_s_set, v_g=v_g_set, v_d_sweep=v_d_set_range))
            elif pattern == "r": # reset
                bias_configs.append(RramSweepConfig(name="reset", v_sub=v_sub, v_s=v_s_reset, v_g=v_g_reset, v_d_sweep=v_d_reset_range))
            else:
                raise ValueError(f"Invalid sweep pattern: {pattern}")

        return bias_configs

    def default_config_string() -> str:
        """Note: values based on a BE device with PMOS access.
        """
        return """
            probe_wl = 1
            probe_sl = 4
            probe_bl = 8
            probe_sub = 9
            v_sub = 0
            v_s_form = 0.0
            v_d_form = 2.5
            v_g_form = -0.6
            v_s_reset = 0.0
            v_d_reset = -2.0
            v_g_reset = -1.5
            v_s_set = 0.0
            v_d_set = 2.0
            v_g_set = -0.6
            v_step = 0.1
            i_compliance_form = 1e-3
            i_compliance_set = 1e-3
            i_compliance_reset = 1e-3
            sequence = "frs"
        """

    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        probe_wl=1,
        probe_sl=4,
        probe_bl=8,
        probe_sub=9,
        v_sub=0.0,                # substrate voltage, constant
        v_s_form=0.0,             # form source voltage, const
        v_d_form=2.5,             # form drain voltage, sweep
        v_g_form=-0.6,            # form gate voltage, const
        v_s_reset=0.0,            # reset source voltage, const
        v_d_reset=-2.0,           # reset drain voltage, sweep
        v_g_reset=-1.5,           # reset gate voltage, const
        v_s_set=0.0,              # set source voltage, const
        v_d_set=2.0,              # set drain voltage, sweep
        v_g_set=-0.6,             # set gate voltage, const
        v_step=0.1,               # voltage step for drain sweeps
        i_compliance_form=10e-3,  # ideally compliance should never hit (transistor should prevent)
        i_compliance_set=10e-3,
        i_compliance_reset=10e-3,
        sequence="frs",
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> MeasurementResult:
        """Run the program."""
        print(f"probe_wl = {probe_wl}")
        print(f"probe_sl = {probe_sl}")
        print(f"probe_bl = {probe_bl}")
        print(f"probe_sub = {probe_sub}")
        print(f"v_sub = {v_sub}")
        print(f"v_s_form = {v_s_form}")
        print(f"v_d_form = {v_d_form}")
        print(f"v_g_form = {v_g_form}")
        print(f"v_s_reset = {v_s_reset}")
        print(f"v_d_reset = {v_d_reset}")
        print(f"v_g_reset = {v_g_reset}")
        print(f"v_s_set = {v_s_set}")
        print(f"v_g_set = {v_g_set}")
        print(f"v_d_set = {v_d_set}")
        print(f"i_compliance_form = {i_compliance_form}")
        print(f"i_compliance_set = {i_compliance_set}")
        print(f"i_compliance_reset = {i_compliance_reset}")
        print(f"sequence = {sequence}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_wl = map_smu_to_slot(smu_slots, probe_wl)
            probe_sl = map_smu_to_slot(smu_slots, probe_sl)
            probe_bl = map_smu_to_slot(smu_slots, probe_bl)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_wl -> {probe_wl}")
            logging.info(f"- probe_sl -> {probe_sl}")
            logging.info(f"- probe_bl -> {probe_bl}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function, closure wrapper with fixed `stop_on_error`` input
        def query_error(instr_b1500):
            _query_error(instr_b1500, stop_on_error)
        
        # convert v_ds and v_gs into a list of values depending on variable object type
        v_d_form_range = into_sweep_range({"start": 0, "stop": v_d_form, "step": v_step})
        v_d_set_range = into_sweep_range({"start": 0, "stop": v_d_set, "step": v_step})
        v_d_reset_range = into_sweep_range({"start": 0, "stop": v_d_reset, "step": v_step})
        
        # number points in each sweep
        num_points_form = len(v_d_form_range)
        num_points_reset = len(v_d_reset_range)
        num_points_set = len(v_d_set_range)
        num_points_max = max(num_points_form, num_points_reset, num_points_set)
        
        # parse sequence into list of sweep bias configs
        num_sequences = len(sequence)
        bias_configs = ProgramKeysightRram1T1R.parse_sweep_sequence(
            sequence=sequence,
            v_sub=v_sub,
            v_s_form=v_s_form,
            v_g_form=v_g_form,
            v_d_form_range=v_d_form_range,
            v_s_set=v_s_set,
            v_g_set=v_g_set,
            v_d_set_range=v_d_set_range,
            v_s_reset=v_s_reset,
            v_g_reset=v_g_reset,
            v_d_reset_range=v_d_reset_range,
        )
        
        # common measurement data block format
        data_measurement = sweep_sequence_data_block(num_sequences=num_sequences, num_points_max=num_points_max)
        # additional program specific data
        data_measurement["sequence"] = sequence
        # add sequence names and npoints for each step
        data_measurement["step_names"] = [ x.name for x in bias_configs ]
        data_measurement["num_points"] = [ x.num_points for x in bias_configs ]

        # measurement compliance settings
        id_compliance = 0.010 # 10 mA complience
        ig_compliance = 0.001 # 1 mA complience
        pow_compliance = abs(id_compliance * np.max(v_d_form_range)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore

        measurement_keysight_b1500_setup(
            instr_b1500=instr_b1500,
            query_error=query_error,
            probe_wl=probe_wl,
            probe_sl=probe_sl,
            probe_bl=probe_bl,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            pow_compliance=pow_compliance,
        )

        data_measurement, cancelled = run_rram_1t1r_sweeps(
            program_name=ProgramKeysightRram1T1R.name,
            instr_b1500=instr_b1500,
            monitor_channel=monitor_channel,
            signal_cancel=signal_cancel,
            sweep_metadata=sweep_metadata,
            query_error=query_error,
            probe_wl=probe_wl,
            probe_sl=probe_sl,
            probe_bl=probe_bl,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            yield_during_measurement=yield_during_measurement,
            bias_configs=bias_configs,
            data_measurement=data_measurement,
        )
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return MeasurementResult(
            cancelled=cancelled,
            data=data_measurement,
        )


class ProgramKeysightRram1T1RSweep(MeasurementProgram):
    """Implement 1T1R gate voltage (wordline) and drain voltage (bitline)
    voltage sweep. Used for determining set/reset points.
    Note this does NOT do a forming step, but this can be used to sweep and
    determine the proper forming voltages.

    Sweep sequence example:
    
    ### FIXED VALUES
    v_g_reset = 0.5
    v_d_reset = -1.0

    ### SWEEP VALUES/ENDPOINTS
    v_g_sweep = [0.5, 0.6, 0.7]
    v_d_sweep = [0.3, 0.5, 0.7]

    [RESET]
    [SET] VG = 0.5 , VD = [0.0, 0.1, 0.2, 0.3]
    [SET] VG = 0.5 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    [SET] VG = 0.5 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    [RESET]
    [SET] VG = 0.6 , VD = [0.0, 0.1, 0.2, 0.3]
    [SET] VG = 0.6 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    [SET] VG = 0.6 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    [RESET]
    [SET] VG = 0.7 , VD = [0.0, 0.1, 0.2, 0.3]
    [SET] VG = 0.7 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    [SET] VG = 0.7 , VD = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    [RESET]
    """
    name = "keysight_rram_1t1r_sweep"

    @staticmethod
    def parse_sweep_sequence(
        v_sub,
        v_s,
        v_g_reset,
        v_d_reset,
        v_g_range,
        v_d_range,
        v_step=0.1, # voltage step for sweeps
    ):
        """Helper function to parse a gate voltage and drain voltage (end point)
        sweep range into a sequence of rram bias configs.
        Made this separate function to make it easier to debug.
        """

        v_d_reset_sweep = into_sweep_range({"start": 0, "stop": v_d_reset, "step": v_step})

        num_points_max = len(v_d_reset_sweep) # to also include reset sequence

        # convert each v_d point into a sweep range
        v_d_sweeps = []
        for v_d in v_d_range:
            v_d_sweep = into_sweep_range({"start": 0, "stop": v_d, "step": v_step})
            num_points_max = max(num_points_max, len(v_d_sweep))
            v_d_sweeps.append(v_d_sweep)
        
        bias_configs = []
        for v_g in v_g_range:
            
            bias_configs.append(RramSweepConfig(
                name="reset",
                v_sub=v_sub,
                v_s=v_s,
                v_g=v_g_reset,
                v_d_sweep=v_d_reset_sweep,
            ))

            for i, v_d in enumerate(v_d_range):
                bias_configs.append(RramSweepConfig(
                    name=f"v_g={v_g}, v_d={v_d}",
                    v_sub=v_sub,
                    v_s=v_s,
                    v_g=v_g,
                    v_d_sweep=v_d_sweeps[i],
                ))
        
        # final reset sweep
        bias_configs.append(RramSweepConfig(
            name="reset",
            v_sub=v_sub,
            v_s=v_s,
            v_g=v_g_reset,
            v_d_sweep=v_d_reset_sweep,
        ))

        return bias_configs, num_points_max
    
    @staticmethod
    def default_config_string() -> str:
        return """
            probe_wl = 1
            probe_sl = 4
            probe_bl = 8
            probe_sub = 9
            v_sub = 0.0
            v_s = 0.0
            v_g_reset = -1.0
            v_d_reset = -2.0
            v_g_range = [0.4, 0.6, 0.8]
            v_d_range = [1.0, 1.5, 2.5]
            v_step = 0.1
        """
    
    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        probe_wl=1,
        probe_sl=4,
        probe_bl=8,
        probe_sub=9,
        v_sub=0.0,                 # substrate voltage, constant
        v_s=0.0,                   # source voltage, constant
        v_g_reset=-1.0,            # fixed reset gate voltage
        v_d_reset=-2.0,            # fixed reset drain voltage
        v_g_range=[0.4, 0.6, 0.8], # gate voltage sweep points
        v_d_range=[1.0, 1.5, 2.5], # drain voltage sweep points
        v_step=0.1,                # voltage step for drain sweeps
        i_d_compliance=10e-3,      # ideally compliance should never hit (transistor should prevent)
        i_g_compliance=1e-3,       # transistor gate current compliance
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> MeasurementResult:
        """Run the program."""
        print(f"probe_wl = {probe_wl}")
        print(f"probe_sl = {probe_sl}")
        print(f"probe_bl = {probe_bl}")
        print(f"probe_sub = {probe_sub}")
        print(f"v_sub = {v_sub}")
        print(f"v_sub = {v_s}")
        print(f"v_g_reset = {v_g_reset}")
        print(f"v_d_reset = {v_d_reset}")
        print(f"v_g_range = {v_g_range}")
        print(f"v_d_range = {v_d_range}")
        print(f"i_d_compliance = {i_d_compliance}")
        print(f"i_g_compliance = {i_g_compliance}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_wl = map_smu_to_slot(smu_slots, probe_wl)
            probe_sl = map_smu_to_slot(smu_slots, probe_sl)
            probe_bl = map_smu_to_slot(smu_slots, probe_bl)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_wl -> {probe_wl}")
            logging.info(f"- probe_sl -> {probe_sl}")
            logging.info(f"- probe_bl -> {probe_bl}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function, closure wrapper with fixed `stop_on_error`` input
        def query_error(instr_b1500):
            _query_error(instr_b1500, stop_on_error)
        
        v_d_sweep = into_sweep_range(v_d_range)
        v_g_sweep = into_sweep_range(v_g_range)

        # parse voltage sweep ranges into list of sweep bias configs
        bias_configs, num_points_max = ProgramKeysightRram1T1RSweep.parse_sweep_sequence(
            v_sub=v_sub,
            v_s=v_s,
            v_g_reset=v_g_reset,
            v_d_reset=v_d_reset,
            v_g_range=v_g_sweep,
            v_d_range=v_d_sweep,
            v_step=v_step,
        )
        num_sequences = len(bias_configs)

        # common measurement data block format
        data_measurement = sweep_sequence_data_block(num_sequences=num_sequences, num_points_max=num_points_max)
        # additional program specific data
        data_measurement["v_d_sweep"] = v_d_sweep
        data_measurement["v_g_sweep"] = v_g_sweep
        # add sequence names and npoints for each step
        data_measurement["step_names"] = [ x.name for x in bias_configs ]
        data_measurement["num_points"] = [ x.num_points for x in bias_configs ]

        # measurement compliance settings
        id_compliance = 0.100 # 100 mA complience
        ig_compliance = 0.010 # 10 mA complience
        pow_compliance = abs(id_compliance * np.max(v_d_sweep)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore

        measurement_keysight_b1500_setup(
            instr_b1500=instr_b1500,
            query_error=query_error,
            probe_wl=probe_wl,
            probe_sl=probe_sl,
            probe_bl=probe_bl,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            pow_compliance=pow_compliance,
        )

        data_measurement, cancelled = run_rram_1t1r_sweeps(
            program_name=ProgramKeysightRram1T1RSweep.name,
            instr_b1500=instr_b1500,
            monitor_channel=monitor_channel,
            signal_cancel=signal_cancel,
            sweep_metadata=sweep_metadata,
            query_error=query_error,
            probe_wl=probe_wl,
            probe_sl=probe_sl,
            probe_bl=probe_bl,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            yield_during_measurement=yield_during_measurement,
            bias_configs=bias_configs,
            data_measurement=data_measurement,
        )
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return MeasurementResult(
            cancelled=cancelled,
            data=data_measurement,
        )


class ProgramKeysightRram1T1RSequence(MeasurementProgram):
    """Implement 1T1R programming sequence. User defines string "codes"
    which define specific programming voltages for gate, drain, and source.
    This program iterates a sequence of codes and measures IV curves.
    This repeats the sequences for multiple repetitions.
    Used for testing multi-bit programming of a 1T1R cell.
    Note: this does not support any "initialization" steps, so user
    will need to manually do a forming step on the 1T1R first.

    Sweep sequence example:
    codes = {
        "reset": {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": -3.0},
        "read":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 0.5},
        "set1":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 2.0},
        "set2":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 2.5},
        "set3":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 3.0},
    }
    sequence = [
        "reset",  # bit = 0
        "read",
        "set1",   # bit = 1
        "read",
        "reset",  # bit = 0
        "read",
        "set2",   # bit = 2
        "read",
        "reset",  # bit = 0
        "read",
        "set3",   # bit = 3
        "read",
    ]
    repeat = 10   # repeat sequence 10 times, emit 10 .h5 dicts

    """
    name = "keysight_rram_1t1r_sequence"

    @staticmethod
    def parse_sweep_sequence(
        codes: dict,
        sequence: list,
        v_step=0.1, # voltage step for sweeps
    ):
        """Helper function to parse user defined codes into rram
        sweep bias configs. Made this separate function to make it
        easier to debug.
        """

        # parse each code into a sweep config
        code_bias_configs = {}
        for code_name, voltages in codes.items():
            if "v_sub" not in voltages or "v_sl" not in voltages or "v_wl" not in voltages or "v_bl" not in voltages:
                raise ValueError(f"Invalid code {code_name} voltage sequence: {voltages}, must be dict containing v_sub, v_sl, v_wl, v_bl")

            v_sub = voltages["v_sub"]
            v_s = voltages["v_sl"]
            v_d = voltages["v_bl"]
            v_g = voltages["v_wl"]
            
            code_bias_configs[code_name] = RramSweepConfig(
                name=code_name,
                v_sub=v_sub,
                v_s=v_s,
                v_g=v_g,
                v_d_sweep=into_sweep_range({"start": 0, "stop": v_d, "step": v_step}),
            )
        
        # parse sequence into a list of bias configs
        num_points_max = 0 # max points in a sweep
        bias_configs = []
        for code_name in sequence:
            if code_name not in code_bias_configs:
                raise ValueError(f"Invalid code name {code_name} in sequence")
            bias = code_bias_configs[code_name]
            bias_configs.append(bias)
            num_points_max = max(num_points_max, len(bias.v_d_sweep))

        return bias_configs, num_points_max

    @staticmethod
    def default_config_string() -> str:
        return """
            probe_wl = 1
            probe_bl = 4
            probe_sl = 8
            probe_sub = 9
            
            [codes]
            reset = { v_sub = 0.0, v_sl = 0.0, v_wl = 0.0, v_bl = -3.0 }
            read =  { v_sub = 0.0, v_sl = 0.0, v_wl = 0.0, v_bl = 0.5 }
            set1 =  { v_sub = 0.0, v_sl = 0.0, v_wl = 0.0, v_bl = 2.0 }
            set2 =  { v_sub = 0.0, v_sl = 0.0, v_wl = 0.0, v_bl = 2.5 }
            set3 =  { v_sub = 0.0, v_sl = 0.0, v_wl = 0.0, v_bl = 3.0 }
            
            [sequence]
            codes = [
                "reset",  # bit = 0
                "read",
                "set1",   # bit = 1
                "read",
                "reset",  # bit = 0
                "read",
                "set2",   # bit = 2
                "read",
                "reset",  # bit = 0
                "read",
                "set3",   # bit = 3
                "read",
            ]
        """
    
    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        path_data_folder="",
        path_save_dir="",
        probe_wl=1,
        probe_sl=4,
        probe_bl=8,
        probe_sub=9,
        codes={
            "reset": {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": -3.0},
            "read":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 0.5},
            "set1":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 2.0},
            "set2":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 2.5},
            "set3":  {"v_sub": 0.0, "v_sl": 0.0, "v_wl": 0.0, "v_bl": 3.0},
        },
        sequence={
            "codes": [
                "reset",  # bit = 0
                "read",
                "set1",   # bit = 1
                "read",
                "reset",  # bit = 0
                "read",
                "set2",   # bit = 2
                "read",
                "reset",  # bit = 0
                "read",
                "set3",   # bit = 3
                "read",
            ]
        },
        repeat=1,
        v_step=0.1,                # voltage step for drain sweeps
        i_d_compliance=10e-3,      # ideally compliance should never hit (transistor should prevent)
        i_g_compliance=1e-3,       # transistor gate current compliance
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> MeasurementResult:
        """Run the program."""
        print(f"probe_wl = {probe_wl}")
        print(f"probe_sl = {probe_sl}")
        print(f"probe_bl = {probe_bl}")
        print(f"probe_sub = {probe_sub}")
        print(f"codes = {codes}")
        print(f"sequence = {sequence}")
        print(f"repeat = {repeat}")
        print(f"i_d_compliance = {i_d_compliance}")
        print(f"i_g_compliance = {i_g_compliance}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_wl = map_smu_to_slot(smu_slots, probe_wl)
            probe_sl = map_smu_to_slot(smu_slots, probe_sl)
            probe_bl = map_smu_to_slot(smu_slots, probe_bl)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_wl -> {probe_wl}")
            logging.info(f"- probe_sl -> {probe_sl}")
            logging.info(f"- probe_bl -> {probe_bl}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function, closure wrapper with fixed `stop_on_error`` input
        def query_error(instr_b1500):
            _query_error(instr_b1500, stop_on_error)

        # parse voltage sweep ranges into list of sweep bias configs
        bias_configs, num_points_max = ProgramKeysightRram1T1RSequence.parse_sweep_sequence(
            codes=codes,
            sequence=sequence["codes"],
            v_step=v_step,
        )
        num_sequences = len(bias_configs)
        num_points_sequence = [ x.num_points for x in bias_configs ]
        step_names = [ x.name for x in bias_configs ]

        # measurement compliance settings
        v_max = 0
        for k, v in codes.items():
            v_max = max(v_max, abs(v["v_sl"]), abs(v["v_wl"]), abs(v["v_bl"]))
        id_compliance = 0.100 # 100 mA complience
        ig_compliance = 0.010 # 10 mA complience
        pow_compliance = abs(id_compliance * np.max(v_max)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore

        measurement_keysight_b1500_setup(
            instr_b1500=instr_b1500,
            query_error=query_error,
            probe_wl=probe_wl,
            probe_sl=probe_sl,
            probe_bl=probe_bl,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            pow_compliance=pow_compliance,
        )

        for n in range(repeat):
            # create new data block for each reptition
            # common measurement data block format
            data_measurement = sweep_sequence_data_block(num_sequences=num_sequences, num_points_max=num_points_max)
            # add sequence names and npoints for each step
            data_measurement["step_names"] = step_names
            data_measurement["num_points"] = num_points_sequence
            
            data_measurement, cancelled = run_rram_1t1r_sweeps(
                program_name=ProgramKeysightRram1T1RSweep.name,
                instr_b1500=instr_b1500,
                monitor_channel=monitor_channel,
                signal_cancel=signal_cancel,
                sweep_metadata=sweep_metadata,
                query_error=query_error,
                probe_wl=probe_wl,
                probe_sl=probe_sl,
                probe_bl=probe_bl,
                probe_sub=probe_sub,
                id_compliance=id_compliance,
                ig_compliance=ig_compliance,
                yield_during_measurement=yield_during_measurement,
                bias_configs=bias_configs,
                data_measurement=data_measurement,
            )

            # save data
            if os.path.exists(path_data_folder):
                path_dir = os.path.join(path_data_folder, path_save_dir)
                os.makedirs(path_dir, exist_ok=True)

                program_name = ProgramKeysightRram1T1RSequence.name
                path_result_h5 = os.path.join(path_dir, f"{program_name}_{n}.h5")
                path_result_mat = os.path.join(path_dir, f"{program_name}_{n}.mat")
                
                export_hdf5(path_result_h5, data_measurement)
                export_mat(path_result_mat, data_measurement)

            # show sequence data
            if monitor_channel is not None:
                monitor_channel.publish({
                    "metadata": {
                        "program": ProgramKeysightRram1T1RSequence.name,
                        "config": sweep_metadata,
                    },
                    "data": dict_np_array_to_json_array(data_measurement), # converts np ndarrays to regular lists
                })

            if signal_cancel is not None and signal_cancel.is_cancelled():
                logging.info(f"[ProgramKeysightRram1T1R] CANCELLING PROGRAM")
                cancelled = True
                break
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return MeasurementResult(
            cancelled=cancelled,
            save_data=False, # dont do save data externally, this is done within the sequence repeat loop
            data=data_measurement,
        )



class ProgramKeysightRram1T1RPulsedForm(MeasurementProgram):
    """TODO: Implement 1T1R pulsed form sweep using bitline voltage at a fixed
    gate bias:

            Vform
             _     _     _     
            | |   | |   | |    
            | |   | |   | |    
       _____| |___| |___| |___ 
                _        
                |
            |---+        
     Vg ---o|      (PMOS)
    = -1 V  |---+        
                |        
                |        
                X        
                X   RRAM 
                X   (BE) 
                |        
                v        
              BE = 0 V

    This sweep will pulse the bitline voltage to try and cause the partial
    breakdown formation in RRAM, then do a read at read voltage for user
    to check resistance:

        for n in range(repeat):
            1. pulse bitline voltage
            2. do read at read voltage (to check resistance)
    """
    name = "keysight_rram_1t1r_pulsed_form"

    @staticmethod
    def default_config_string() -> str:
        return """
            probe_wl = 1
            probe_sl = 4
            probe_bl = 8
            probe_sub = 9
            v_sub = 0
            v_s_form = 0.0
            v_d_form = 2.5
            v_g_form = -0.6
            v_s_read = 0.0
            v_d_read = 0.5
            v_g_read = -1.0
            repeat = 1
            v_step = 0.1
        """
    
    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        path_data_folder="",
        path_save_dir="",
        probe_wl=1,
        probe_sl=4,
        probe_bl=8,
        probe_sub=9,
        v_sub=0.0,
        v_s_form=0.0,
        v_d_form=2.5,
        v_g_form=-0.6,
        v_s_read=0.0,
        v_d_read=0.5,
        v_g_read=-1.0,
        repeat=1,
        v_step=0.1,                # voltage step for drain sweeps
        i_d_compliance=10e-3,      # ideally compliance should never hit (transistor should prevent)
        i_g_compliance=1e-3,       # transistor gate current compliance
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> MeasurementResult:
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_wl = map_smu_to_slot(smu_slots, probe_wl)
            probe_sl = map_smu_to_slot(smu_slots, probe_sl)
            probe_bl = map_smu_to_slot(smu_slots, probe_bl)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_wl -> {probe_wl}")
            logging.info(f"- probe_sl -> {probe_sl}")
            logging.info(f"- probe_bl -> {probe_bl}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function, closure wrapper with fixed `stop_on_error`` input
        def query_error(instr_b1500):
            _query_error(instr_b1500, stop_on_error)

        id_compliance = 0.100 # 100 mA complience
        ig_compliance = 0.010 # 10 mA complience
        pow_compliance = abs(id_compliance * np.max(v_d_form)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return MeasurementResult(
            cancelled=cancelled,
            save_data=False, # dont do save data externally, this is done within the sequence repeat loop
            data=data_measurement,
        )

if __name__ == "__main__":
    """Tests running the program
    """
    import os
    from scipy.io import savemat
    from controller.util.io import export_hdf5

    # res = "NCT+5.55189E+00,NCI+0.00005E-09,NAT+5.66104E+00,NAI+0.00000E-09,NHT+5.77022E+00,NHI+0.00010E-09,WHV-1.20000E+00,NCT+5.83624E+00,NCI+0.00000E-09,NAT+5.85902E+00,NAI+0.00000E-09,NHT+5.96819E+00,NHI+0.00015E-09,WHV-1.10000E+00,NCT+6.03426E+00,NCI+0.00000E-09,NAT+6.05703E+00,NAI+0.00010E-09,NHT+6.16623E+00,NHI+0.00000E-09,WHV-1.00000E+00,NCT+6.23234E+00,NCI+0.00000E-09,NAT+6.25518E+00,NAI+0.00000E-09,NHT+6.36435E+00,NHI+0.00010E-09,WHV-0.90000E+00,NCT+6.43042E+00,NCI+0.00005E-09,NAT+6.45328E+00,NAI+0.00005E-09,NHT+6.56246E+00,NHI+0.00005E-09,WHV-0.80000E+00,NCT+6.62855E+00,NCI+0.00015E-09,NAT+6.65140E+00,NAI+0.00005E-09,NHT+6.76060E+00,NHI+0.00010E-09,WHV-0.70000E+00,NCT+6.82667E+00,NCI+0.00000E-09,NAT+6.84944E+00,NAI+0.00000E-09,NHT+6.95864E+00,NHI+0.00015E-09,WHV-0.60000E+00,NCT+7.02471E+00,NCI+0.00010E-09,NAT+7.04756E+00,NAI+0.00005E-09,NHT+7.15675E+00,NHI+0.00010E-09,WHV-0.50000E+00,NCT+7.22284E+00,NCI+0.00005E-09,NAT+7.24569E+00,NAI-0.00010E-09,NHT+7.35487E+00,NHI+0.00000E-09,WHV-0.40000E+00,NCT+7.42094E+00,NCI+0.00010E-09,NAT+7.44379E+00,NAI+0.00015E-09,NHT+7.55299E+00,NHI+0.00010E-09,WHV-0.30000E+00,NCT+7.61906E+00,NCI+0.00005E-09,NAT+7.64190E+00,NAI+0.00010E-09,NHT+7.75107E+00,NHI+0.00015E-09,WHV-0.20000E+00,NCT+7.81712E+00,NCI+0.00000E-09,NAT+7.83997E+00,NAI+0.00010E-09,NHT+7.94907E+00,NHI+0.00005E-09,WHV-0.10000E+00,NCT+8.01521E+00,NCI+0.00000E-09,NAT+8.03806E+00,NAI+0.00010E-09,NHT+8.14722E+00,NHI+0.00015E-09,WHV+0.00000E+00,NCT+8.21331E+00,NCI+0.00000E-09,NAT+8.23608E+00,NAI-0.00005E-09,NHT+8.34523E+00,NHI+0.00000E-09,WHV+0.10000E+00,NCT+8.41130E+00,NCI+0.00000E-09,NAT+8.43407E+00,NAI+0.00010E-09,NHT+8.54324E+00,NHI+0.00015E-09,WHV+0.20000E+00,NCT+8.60933E+00,NCI+0.00000E-09,NAT+8.63209E+00,NAI+0.00015E-09,NHT+8.74126E+00,NHI+0.00015E-09,WHV+0.30000E+00,NCT+8.80730E+00,NCI+0.00000E-09,NAT+8.83016E+00,NAI+0.00005E-09,NHT+8.93933E+00,NHI+0.00010E-09,WHV+0.40000E+00,NCT+9.00542E+00,NCI+0.00010E-09,NAT+9.02826E+00,NAI+0.00000E-09,NHT+9.13741E+00,NHI+0.00015E-09,WHV+0.50000E+00,NCT+9.20348E+00,NCI+0.00000E-09,NAT+9.22632E+00,NAI+0.00010E-09,NHT+9.33545E+00,NHI+0.00005E-09,WHV+0.60000E+00,NCT+9.40154E+00,NCI+0.00000E-09,NAT+9.42431E+00,NAI+0.00000E-09,NHT+9.53348E+00,NHI+0.00010E-09,WHV+0.70000E+00,NCT+9.59954E+00,NCI-0.00005E-09,NAT+9.62241E+00,NAI+0.00010E-09,NHT+9.73154E+00,NHI+0.00000E-09,WHV+0.80000E+00,NCT+9.79756E+00,NCI+0.00010E-09,NAT+9.82043E+00,NAI+0.00005E-09,NHT+9.92957E+00,NHI+0.00015E-09,WHV+0.90000E+00,NCT+9.99564E+00,NCI+0.00010E-09,NAT+1.00184E+01,NAI+0.00015E-09,NHT+1.01276E+01,NHI+0.00000E-09,WHV+1.00000E+00,NCT+1.01936E+01,NCI+0.00005E-09,NAT+1.02165E+01,NAI+0.00015E-09,NHT+1.03256E+01,NHI+0.00015E-09,WHV+1.10000E+00,NCT+1.03917E+01,NCI+0.00000E-09,NAT+1.04145E+01,NAI+0.00005E-09,NHT+1.05236E+01,NHI+0.00005E-09,EHV+1.20000E+00"
    # print(res)
    # vals = res.strip().split(",")
    # vals = parse_keysight_str_values(vals)
    # print(vals)

    # val_table = []
    # for vals_chunk in iter_chunks(vals, 7):
    #     print(vals_chunk)
    #     val_table.append(["0.05", vals_chunk[6], vals_chunk[1], vals_chunk[3], vals_chunk[5]])
    
    # print(tabulate(val_table, headers=["v_ds [V]", "v_gs [V]", "i_d [A]", "i_s [A]", "i_g [A]"]))

    # exit()

    rm = pyvisa.ResourceManager()
    print(rm.list_resources())

    instr_b1500 = rm.open_resource(
        "GPIB0::16::INSTR",
        read_termination="\n",
        write_termination="\n",
    )

    print(instr_b1500.query("*IDN?"))
    instr_b1500.write("*RST")

    def run_measurement():
        print("RUNNING TASK")
        try:
            result = ProgramKeysightRram1T1R.run(
                instr_b1500=instr_b1500,
                probe_wl=1,
                probe_sl=4,
                probe_bl=8,
                v_d_form=2.0,
                v_d_set=1.5,
                v_d_reset=-2.0,
                v_g_form=-1.4,
                v_g_set=-1.4,
                v_g_reset=-1.4,
                sequence="frsrs",
            )
            # print(result)
            os.makedirs("debug", exist_ok=True)
            savemat(os.path.join("debug", "keysight_rram_1t1r.mat"), result, appendmat=False)
            export_hdf5(os.path.join("debug", "keysight_rram_1t1r.h5"), result)
        except Exception as err:
            print(f"Measurement FAILED: {err}")
            instr_b1500.write(f"DZ") # ensure channels are zero-d
            print(traceback.format_exc())

        
    task = gevent.spawn(run_measurement)
    gevent.joinall([task])

    # done, turn off
    print("MEASUREMENT DONE, TURNING OFF SMUs WITH CL")
    instr_b1500.write("CL")