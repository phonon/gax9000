import traceback
import os
import numpy as np
import gevent
import pyvisa
import logging
from time import time
from dataclasses import dataclass
from tabulate import tabulate
from controller.programs import MeasurementProgram, MeasurementResult, SweepType
from controller.sse import EventChannel
from controller.util import into_sweep_range, parse_keysight_str_values, iter_chunks, map_smu_to_slot, dict_np_array_to_json_array, exp_moving_avg_with_init
from controller.util.io import export_hdf5, export_mat

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
    probe_t: int,
    probe_b: int,
    probe_sub: int,
    i_compliance: float,
    range_mode: str = "1na",
    adc_type: str = "hispeed",
    adc_mode: str = "auto",
    adc_sampling_coeff = 30,
    t_hold = 0.010,  # 10 ms
    t_delay = 0.010, # 10 ms, seems OK. if this is not 0, then it seems like first measurement is much lower than the others
    t_sdelay = 0,    # step delay
):
    """Standard shared setup for 2 terminal IV measurements.
    """

    # enable channels: CN (pg 4-62)
    instr_b1500.write(f"CN {probe_sub},{probe_t},{probe_b}")
    query_error(instr_b1500)

    instr_b1500.write("FMT 1,1") # clear data buffer and set format (4-24, 4-25)
    instr_b1500.write("TSC 1")   # enables timestamp output
    instr_b1500.write("FL 0")    # set filter off
    query_error(instr_b1500)

    # instr_b1500.write("AV 10,1") # sets ADC number of samples for 1 data
    # query_error(instr_b1500)

    # select type of A/D converter (4-33, pg 353):
    #   ADD channel,type
    ADC_TYPE = {
        "hispeed": 0,
        "hires": 1,
        "pulse": 2,
    }
    adc_type_int = ADC_TYPE[adc_type.lower()]
    instr_b1500.write(f"AAD {probe_t},{adc_type_int}")
    instr_b1500.write(f"AAD {probe_b},{adc_type_int}")
    instr_b1500.write(f"AAD {probe_sub},{adc_type_int}")
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
    ADC_HISPEED_MODES = {
        "auto": 0,
        "manual": 1,
        "power_line_cycle": 2,
        "plc": 2,
        "measurement_time": 3,
    }
    adc_mode_int = ADC_HISPEED_MODES[adc_mode.lower()]
    instr_b1500.write(f"AIT {adc_type_int},{adc_mode_int},{adc_sampling_coeff}")
    query_error(instr_b1500)

    # zero voltage to probes, DV (pg 4-78) cmd sets DC voltage on channels:
    #   DV {probe},{vrange},{v},{icompliance}
    instr_b1500.write(f"DV {probe_sub},0,0,{i_compliance}")
    instr_b1500.write(f"DV {probe_t},0,0,{i_compliance}")
    instr_b1500.write(f"DV {probe_b},0,0,{i_compliance}")
    query_error(instr_b1500)

    # set measurement mode to multi-channel staircase sweep (MODE = 16) (4-151, pg 471):
    #   MM mode,ch0,ch1,ch2,...
    mm_mode = 16
    instr_b1500.write(f"MM {mm_mode},{probe_t},{probe_b}");
    query_error(instr_b1500)

    # set probe current measurement mode (4-62, pg 382):
    #   CMM ch,mode
    CMM_MODE_COMPLIANCE = 0
    CMM_MODE_CURRENT = 1
    CMM_MODE_VOLTAGE = 2
    CMM_MODE_FORCE = 3
    CMM_MODE_SYNC = 4
    cmm_mode = CMM_MODE_CURRENT
    instr_b1500.write(f"CMM {probe_t},{cmm_mode}")
    instr_b1500.write(f"CMM {probe_b},{cmm_mode}")
    query_error(instr_b1500)

    # set auto-ranging (4-183 pg 503, page 339 for modes)
    RANGE_MODES = {
        "auto": 0,      # auto

        # limited auto range modes
        "1pa": 8,       # 1 pA limited auto
        "10pa": 9,      # 10 pA limited auto
        "100pa": 10,    # 100 pA limited auto
        "1na": 11,      # 1 nA limited auto
        "10na": 12,     # 10 nA limited auto
        "100na": 13,    # 100 nA limited auto
        "1ua": 14,      # 1 uA limited auto
        "10ua": 15,     # 10 uA limited auto
        "100ua": 16,    # 100 uA limited auto
        "1ma": 17,      # 1 mA limited auto
        "10ma": 18,     # 10 mA limited auto

        # fixed range modes
        "fixed_1pa": -8,      # 1 pA fixed
        "fixed_10pa": -9,     # 10 pA fixed
        "fixed_100pa": -10,   # 100 pA fixed
        "fixed_1na": -11,     # 1 nA fixed
        "fixed_10na": -12,    # 10 nA fixed
        "fixed_100na": -13,   # 100 nA fixed
        "fixed_1ua": -14,     # 1 uA fixed
        "fixed_10ua": -15,    # 10 uA fixed
        "fixed_100ua": -16,   # 100 uA fixed
        "fixed_1ma": -17,     # 1 mA fixed
        "fixed_10ma": -18,    # 10 mA fixed
    }
    range_mode_int = RANGE_MODES[range_mode.lower()]
    instr_b1500.write(f"RI {probe_t},{range_mode_int}")
    instr_b1500.write(f"RI {probe_b},{range_mode_int}")
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
    instr_b1500.write(f"WT {t_hold},{t_delay},{t_sdelay}")
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


@dataclass
class IV2TermConfig:
    sweep_terminal: str # either "t" or "b" for top or bottom
    probe_sweep: int
    probe_const: int
    v_sweep_range: list[float]
    v_const: float
    pattern: list[SweepType]

@dataclass
class IV2TermSweep:
    index: int
    sweep_type: SweepType
    sweep_terminal: str # either "t" or "b" for top or bottom
    probe_sweep: int
    probe_const: int
    v_sweep_range: list[float]
    v_const: float

def parse_iv2term_sequence(
    probe_t: int,
    probe_b: int,
    code: dict,
    sequence: list[str],
) -> tuple[list[IV2TermSweep], int, int]:
    """Parse sequence into list of IV2TermConfig which contains standard
    format for determining sweep in B1500.
    Returns:
    - sweep sequence list
    - number of sweep steps
    - number of voltage measurement points 
    """
    # parse each code into IV2TermConfig
    sweep_configs: dict[str, IV2TermConfig] = {}
    for code_name, code_config in code.items():
        # determine if top or bottom is const
        if isinstance(code_config["v_t"], float):
            # top const, bottom sweep
            sweep_terminal = "b"
            probe_sweep = probe_b
            v_sweep = into_sweep_range(code_config["v_b"])
            probe_const = probe_t
            v_const = code_config["v_t"]
        else:
            # bottom const, top sweep
            sweep_terminal = "t"
            probe_sweep = probe_t
            v_sweep = into_sweep_range(code_config["v_t"])
            probe_const = probe_b
            v_const = code_config["v_b"]
        pattern = SweepType.parse_string(code_config["pattern"])
        
        sweep_configs[code_name] = IV2TermConfig(
            sweep_terminal=sweep_terminal,
            probe_sweep=probe_sweep,
            probe_const=probe_const,
            v_sweep_range=v_sweep,
            v_const=v_const,
            pattern=pattern,
        )

    # parse sequence into list of IV2TermSweep
    idx = 0 # global sweep index
    num_points = 0 # max number of points in any sweep
    sweeps: list[IV2TermSweep] = []
    for code_name in sequence:
        sweep_config = sweep_configs[code_name]
        for (i, sweep_type) in SweepType.iter_with_sweep_index(sweep_config.pattern):
            sweeps.append(IV2TermSweep(
                index=idx,
                sweep_type=sweep_type,
                sweep_terminal=sweep_config.sweep_terminal,
                probe_sweep=sweep_config.probe_sweep,
                probe_const=sweep_config.probe_const,
                v_sweep_range=sweep_config.v_sweep_range,
                v_const=sweep_config.v_const,
            ))
            num_points = max(num_points, len(sweep_config.v_sweep_range))
            idx += sweep_type.size()
    
    num_sweeps = idx
    
    return sweeps, num_sweeps, num_points


class ProgramKeysightIV2TermSequence(MeasurementProgram):
    """Implement a two terminal top-bottom IV sweep. 

       Top                 Bottom
               | 0  0 |
       v_t ----|0 0  0|---- v_b
               | 0  0 |
    
               Material
    
    Reference program for Farnaz group.
    """
    name = "keysight_iv_2term_sequence"

    @staticmethod
    def default_config_string() -> str:
        return """
            probe_t = 1
            probe_b = 2
            probe_sub = 9
            
            ### current compliance
            i_compliance = 0.001
            
            ### range mode:
            ### limited auto: auto, 1pa, 10pa, 100pa, 1na, 10na, 100na, 1ua, ...
            ### fixed modes: fixed_1pa, fixed_10pa, ...
            range_mode = "1na"

            ### adc type: hispeed, hires, pulse
            ### adc mode: auto, manual, plc, measurement_time
            ### adc_sampling_coeff: integration time or the number of avg samples
            ### (see b1500 manual)
            # adc_type = "hispeed"
            # adc_mode = "auto"
            # adc_sampling_coeff = 30

            ### waveform settings:
            # | hold       | force | delay | Sdelay      | force | delay | Sdelay      |
            #                              | measure |                   | measure |
            #              |<----- repeat -------------->|
            ### (see b1500 manual)
            # t_hold = 0.010 
            # t_delay = 0.010
            # t_sdelay = 0
        
            ### code definitions
            # pattern = "frfr..." # f = forward, r = reverse
            # v_t = top voltage value or sweep
            # v_b = bottom voltage value or sweep
            # either v_t or v_b must be an array, other must be constant

            [code.pos1fr]
            pattern = "fr"
            v_t = { start = 0.0, stop = 1.0, step = 0.1 }
            v_b = 0.0

            [code.neg1fr]
            pattern = "fr"
            v_t = { start = 0.0, stop = -1.0, step = 0.1 }
            v_b = 0.0
            
            [code.pos5fr]
            pattern = "frfrfrfrfr"
            v_t = { start = 0.0, stop = 1.0, step = 0.1 }
            v_b = 0.0

            [code.neg5fr]
            pattern = "frfrfrfrfr"
            v_t = { start = 0.0, stop = -1.0, step = 0.1 }
            v_b = 0.0

            ### sweep sequence
            [sequence]
            codes = [
                "pos1fr",
                "neg1fr",
            ]
        """
    
    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel = None,
        sweep_metadata: dict = {},
        probe_t = 1,
        probe_b = 2,
        probe_sub = 9,
        v_sub = 0, # substrate bias
        i_compliance = 10e-3,   # ideally compliance should never hit (transistor should prevent)
        pow_compliance = None,  # manual power compliance
        range_mode = "1na",
        adc_type = "hispeed",
        adc_mode = "auto",
        adc_sampling_coeff = 30,
        t_hold = 0.010,
        t_delay = 0.010,
        t_sdelay = 0,
        timeout = 60, # timeout in seconds for each measurement step
        code={
            "pos1fr": {"pattern": "fr", "sweep": "t", "v_t": 1.0, "v_b": 0.0, "v_step": 0.1},
            "neg1fr": {"pattern": "fr", "sweep": "t", "v_t": -1.0, "v_b": 0.0, "v_step": 0.1},
        },
        sequence={
            "codes": [
                "pos1fr",
                "neg1fr",
            ]
        },
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> MeasurementResult:
        """Run the program."""
        print(f"probe_t = {probe_t}")
        print(f"probe_b = {probe_b}")
        print(f"probe_sub = {probe_sub}")
        print(f"v_sub = {v_sub}")
        print(f"i_d_compliance = {i_compliance}")
        print(f"pow_compliance = {pow_compliance}")
        print(f"range_mode = {range_mode}")
        print(f"adc_type = {adc_type}")
        print(f"adc_mode = {adc_mode}")
        print(f"adc_sampling_coeff = {adc_sampling_coeff}")
        print(f"t_hold = {t_hold}")
        print(f"t_delay = {t_delay}")
        print(f"t_sdelay = {t_sdelay}")
        print(f"code = {code}")
        print(f"sequence = {sequence}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_t = map_smu_to_slot(smu_slots, probe_t)
            probe_b = map_smu_to_slot(smu_slots, probe_b)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_t -> {probe_t}")
            logging.info(f"- probe_b -> {probe_b}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function, closure wrapper with fixed `stop_on_error`` input
        def query_error(instr_b1500):
            _query_error(instr_b1500, stop_on_error)

        # parse sequence into list of individual sweep codes
        sweeps, num_sweeps, num_points = parse_iv2term_sequence(
            probe_t = probe_t,
            probe_b = probe_b,
            code = code,
            sequence = sequence["codes"],
        )

        data_shape = (num_sweeps, num_points)

        # data output
        v_t_out = np.full(data_shape, np.nan)
        v_b_out = np.full(data_shape, np.nan)
        i_t_out = np.full(data_shape, np.nan)
        i_b_out = np.full(data_shape, np.nan)
        # timestamps
        time_i_t_out = np.full(data_shape, np.nan)
        time_i_b_out = np.full(data_shape, np.nan)
        # number of points in each sweep vector, rest are padded with nan
        points_out = np.full((num_sweeps, 1), np.nan)

        # measurement power compliance settings
        # TODO: currently not used for anything
        if pow_compliance is None:
            v_max = 0
            for x in sweeps:
                v_max = max(v_max, np.max(np.abs(np.array(x.v_sweep_range))))
            pow_compliance = abs(i_compliance * v_max) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore

        measurement_keysight_b1500_setup(
            instr_b1500=instr_b1500,
            query_error=query_error,
            probe_b=probe_b,
            probe_t=probe_t,
            probe_sub=probe_sub,
            i_compliance=i_compliance,
            range_mode=range_mode,
            adc_type=adc_type,
            adc_mode=adc_mode,
            adc_sampling_coeff=adc_sampling_coeff,
            t_hold=t_hold,
            t_delay=t_delay,
            t_sdelay=t_sdelay,
        )

        # ===========================================================
        # PERFORM SWEEP FOR EACH SEQUENCE
        # ===========================================================

        # sweep state
        t_run_avg = None  # avg program step time
        cancelled = False # flag for program cancelled before done

        for sweep in sweeps:
            sweep_type = sweep.sweep_type
            # swept probe tip
            sweep_terminal = sweep.sweep_terminal
            probe_sweep = sweep.probe_sweep
            v_sweep = sweep.v_sweep_range
            points_sweep = len(v_sweep)
            # constant bias probe tip
            probe_const = sweep.probe_const
            v_const = sweep.v_const
            idx = sweep.index

            print(f"==============================")
            print(f"Measuring step {idx+1}/{num_sweeps}")
            print(f"------------------------------")
            
            # write voltage staircase waveform
            wv_range_mode = 0 # AUTO
            cmd = sweep_type.b1500_wv_sweep_command(
                ch=probe_sweep,
                range=wv_range_mode,
                start=v_sweep[0],
                stop=v_sweep[-1],
                steps=points_sweep,
                icomp=i_compliance,
                pcomp=None, # can trigger false errors
            )
            instr_b1500.write(cmd)
            query_error(instr_b1500)
            
            # write non-swept const probe bias
            instr_b1500.write(f"DV {probe_const},0,{v_const},{i_compliance}")
            query_error(instr_b1500)
            
            # write substrate bias
            instr_b1500.write(f"DV {probe_sub},0,{v_sub},{i_compliance}")
            query_error(instr_b1500)
            
            # execute and wait for data response
            instr_b1500.write("XE")

            # starting time for step
            t_start = time()

            # yield green thread during measurement to let other tasks run
            if yield_during_measurement and t_run_avg is not None and t_run_avg > 0:
                t_sleep = 0.9 * t_run_avg
                logging.info(f"[ProgramKeysightIdVgs] SLEEPING: gevent.sleep({t_sleep:.3f})")
                gevent.sleep(t_sleep)
            
            # set timeout (milliseconds)
            instr_b1500.timeout = timeout * 1000
            _opc = instr_b1500.query("*OPC?")
            instr_b1500.timeout = 10 * 1000
            query_error(instr_b1500)

            # update avg measurement time for accurate gevent sleep
            t_finish = time()
            t_run = t_finish - t_start
            t_run_avg = max(0, exp_moving_avg_with_init(t_run_avg, t_run, alpha=0.2, init_alpha=0.9))

            # zero probes after measurement
            instr_b1500.write(f"DV {probe_sub},0,0,{i_compliance}")
            instr_b1500.write(f"DV {probe_t},0,0,{i_compliance}")
            instr_b1500.write(f"DV {probe_b},0,0,{i_compliance}")
            query_error(instr_b1500)
            
            # number of bytes in output data buffer
            nbytes = int(instr_b1500.query("NUB?"))
            # print(f"nbytes={nbytes}") # debug
            buf = instr_b1500.read()
            # print(buf) # debug

            # parse vals strings into numbers
            vals = buf.strip().split(",")
            vals = parse_keysight_str_values(vals)

            # values chunked for each measurement point:
            #   [ [tt0, it0, tb0, ib0, vsw0] , [tt1, it1, tb1, ib1, vsw1], ... ]
            val_chunks = [ x for x in iter_chunks(vals, 5) ]
            # print(val_chunks) # debug

            # split val chunks into forward/reverse sweep components:
            if sweep_type == SweepType.FORWARD or sweep_type == SweepType.REVERSE:
                sweep_chunks = [val_chunks]
            elif sweep_type == SweepType.FORWARD_REVERSE or sweep_type == SweepType.REVERSE_FORWARD:
                sweep_chunks = [val_chunks[0:points_sweep], val_chunks[points_sweep:]]
            
            val_table = [] # values to print out to console for display

            for s, sweep_vals in enumerate(sweep_chunks):
                for i, vals_chunk in enumerate(sweep_vals):
                    # determine top and bottom value based on sweep terminal

                    if sweep_terminal == "t":
                        v_t_val = vals_chunk[4]
                        v_b_val = v_const
                        i_t_val = vals_chunk[1]
                        i_b_val = vals_chunk[3]
                        time_i_t_val = vals_chunk[0]
                        time_i_b_val = vals_chunk[2]
                    else: # == "b"
                        v_t_val = v_const
                        v_b_val = vals_chunk[4]
                        i_t_val = vals_chunk[1]
                        i_b_val = vals_chunk[3]
                        time_i_t_val = vals_chunk[0]
                        time_i_b_val = vals_chunk[2]
                    
                    v_t_out[idx + s, i] = v_t_val
                    v_b_out[idx + s, i] = v_b_val
                    i_t_out[idx + s, i] = i_t_val
                    i_b_out[idx + s, i] = i_b_val
                    # timestamps
                    time_i_t_out[idx + s, i] = time_i_t_val
                    time_i_b_out[idx + s, i] = time_i_b_val
                    # number of voltage sweep points
                    points_out[idx + s, 0] = points_sweep
            
                    val_table.append([v_t_val, v_b_val, i_t_val, i_b_val])
            

            print(tabulate(val_table, headers=["v_t [V]", "v_b [V]", "i_t [A]", "i_b [A]"]))

            idx_finished = idx + len(sweep_chunks)
            print("------------------------------")
            print(f"Finished step {idx_finished+1}/{num_sweeps}")
            print("==============================")

            # after each step completes, send partial update
            if monitor_channel is not None and idx < num_sweeps-1: # don't publish last step
                def task_update_program_status():
                    """Update program status."""
                    data={
                        "v_t": v_t_out,
                        "v_b": v_b_out,
                        "i_t": i_t_out,
                        "i_b": i_b_out,
                        "time_i_t": time_i_t_out,
                        "time_i_b": time_i_b_out,
                        "points": points_out,
                    }
                    data_cleaned = dict_np_array_to_json_array(data) # converts np ndarrays to regular lists and replace nan

                    monitor_channel.publish({
                        "metadata": {
                            "program": ProgramKeysightIV2TermSequence.name,
                            "config": sweep_metadata,
                            "step": idx_finished,
                            "step_total": num_sweeps,
                        },
                        "data": data_cleaned,
                    })
                    
                gevent.spawn(task_update_program_status)

            # break after bias finished if cancelled
            if signal_cancel is not None and signal_cancel.is_cancelled():
                logging.info(f"[ProgramKeysightIV2TermSequence] CANCELLING PROGRAM")
                cancelled = True
                break
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return MeasurementResult(
            cancelled=cancelled,
            save_data=True, # save partial data even if cancelled
            data={
                "v_t": v_t_out,
                "v_b": v_b_out,
                "i_t": i_t_out,
                "i_b": i_b_out,
                "time_i_t": time_i_t_out,
                "time_i_b": time_i_b_out,
                "points": points_out,
            },
        )


if __name__ == "__main__":
    # DEBUGGING: test config parsing
    config = ProgramKeysightIV2TermSequence.default_config()
    print(config)

    code = config["code"]
    sequence = config["sequence"]

    sweeps, num_sweeps, num_points = parse_iv2term_sequence(
        probe_t = 1,
        probe_b = 2,
        code = code,
        sequence = sequence["codes"],
    )
    
    data_shape = (num_sweeps, num_points)
    print(f"data_shape = {data_shape}")

    for sweep in sweeps:
        print(f"[{sweep.index}] {sweep}")
