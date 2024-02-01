"""
Implement CMOS DC voltage sweeps

E.g. Logic 1-terminal measurement (inverter)
Input: Va
Output: Vo
Supply: VDD, VSS

                VDD
                _
                |        
            |---+        
     Va ---o|      (PMOS)
    = -1 V  |---+        
                |______ Vo 
                |        
            |---+        
     Va ----|      (NMOS)
    = -1 V  |---+        
                |        
                v        
                VSS

E.g. Logic 2-terminal measurement (e.g. NAND2)
Inputs: Va, Vb
Output: Vo
Supply: VDD, VSS
                VDD           VDD
                _              _
                |              |        
            |---+          |---+        
     Va ---o|       Vb ---o|      (PMOS)
            |---+          |---+ 
                |______________|______ Vo
                |        
            |---+        
     Va ----|      (NMOS)
            |---+
                |    
            |---+        
     Vb ----|      (NMOS)
            |---+        
                |
                v        
                VSS

For any logic case:
- VDD, VSS are constant DC bias
- One input (Va or Vb) is swept while other is constant
- Output Vo is measured
"""

import logging
import traceback
import numpy as np
import gevent
import logging
from time import time
from tabulate import tabulate
from controller.sse import EventChannel
from controller.programs import MeasurementProgram, MeasurementResult, SweepType
from controller.util import into_sweep_range, parse_keysight_str_values, iter_chunks, map_smu_to_slot, exp_moving_avg_with_init, dict_np_array_to_json_array


def measurement_keysight_b1500_setup_cmos(
    instr_b1500,
    query_error,
    num_inputs: int,
    probe_a: int,
    probe_b: int,
    probe_out: int,
    probe_vdd: int,
    probe_vss: int,
    probe_sub: int,
    id_compliance: float,
    ig_compliance: float,
    pow_compliance: float,
):
    """Standard shared setup for FET IV measurements.
    """
    # reset instrument
    instr_b1500.write("*RST")
    instr_b1500.query("ERRX?") # clear any existing error message and ignore

    all_probes_str = f"{probe_sub},{probe_vdd},{probe_vss},{probe_out},{probe_a}"
    if num_inputs == 2:
        all_probes_str += f",{probe_b}"

    # enable channels: CN (pg 4-62)
    cn_str = f"CN {probe_sub},{probe_vdd},{probe_vss},{probe_out},{probe_a}"
    if num_inputs == 1:
        input_probes = [probe_a,]
    elif num_inputs == 2:
        input_probes = [probe_a, probe_b]
        cn_str += f",{probe_b}"
    else:
        raise ValueError(f"Invalid num_input = {num_inputs}, must be 1 or 2")
    instr_b1500.write(cn_str)
    query_error(instr_b1500)

    instr_b1500.write("FMT 1,1") # clear data buffer and set format (4-24, 4-25)
    instr_b1500.write("TSC 1")   # enables timestamp output
    instr_b1500.write("FL 0")    # set filter off
    query_error(instr_b1500)

    # instr_b1500.write("AV 10,1") # sets ADC number of samples for 1 data
    # query_error(instr_b1500)
    print("AAD")
    # select type of A/D converter (4-33, pg 353):
    #   ADD channel,type
    ADC_TYPE_HISPEED = 0
    ADC_TYPE_HIRES = 1
    ADC_TYPE_PULSE = 2
    for probe in [probe_sub, probe_vdd, probe_vss, probe_out] + input_probes:
        instr_b1500.write(f"AAD {probe},{ADC_TYPE_HISPEED}")
        query_error(instr_b1500)

    print("AIT")

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

    adc_hires_mode = ADC_HISPEED_MODE_AUTO
    adc_hires_sampling_coeff = 30
    instr_b1500.write(f"AIT {ADC_TYPE_HIRES},{adc_hires_mode},{adc_hires_sampling_coeff}")
    query_error(instr_b1500)

    # TODO: set pulsed ADC mode?

    print("DV")

    # zero voltage to probes, DV (pg 4-78) cmd sets DC voltage on channels:
    #   DV {probe},{vrange},{v},{icompliance}

    for probe in (probe_sub, probe_vdd, probe_vss, probe_out):
        instr_b1500.write(f"DV {probe},0,0,{id_compliance}")
        print(f"DV {probe},0,0,{id_compliance}")
        query_error(instr_b1500)
    
    for probe in input_probes:
        instr_b1500.write(f"DV {probe},0,0,{ig_compliance}")
        print(f"DV {probe},0,0,{ig_compliance}")
        query_error(instr_b1500)

    # set measurement mode to multi-channel staircase sweep (MODE = 16) (4-151, pg 471):
    # MM mode,ch0,ch1,ch2,...
    print("MM")
    mm_mode = 16
    instr_b1500.write(f"MM {mm_mode},{all_probes_str}")
    query_error(instr_b1500)

    # set probe current measurement mode (4-62, pg 382):
    #   CMM ch,mode
    CMM_MODE_COMPLIANCE = 0
    CMM_MODE_CURRENT = 1
    CMM_MODE_VOLTAGE = 2
    CMM_MODE_FORCE = 3
    CMM_MODE_SYNC = 4
    # measure output voltage
    instr_b1500.write(f"CMM {probe_out},{CMM_MODE_VOLTAGE}")
    # measure current through inputs: vdd, vss, a, b
    instr_b1500.write(f"CMM {probe_vdd},{CMM_MODE_CURRENT}")
    instr_b1500.write(f"CMM {probe_vss},{CMM_MODE_CURRENT}")
    instr_b1500.write(f"CMM {probe_a},{CMM_MODE_CURRENT}")
    if num_inputs == 2:
        instr_b1500.write(f"CMM {probe_b},{CMM_MODE_CURRENT}")
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
    RANGE_MODE_100UA_FIXED = -17 # 100 uA range fixed
    range_mode = RANGE_MODE_1NA
    for probe in (probe_vdd, probe_vss, probe_a):
        instr_b1500.write(f"RI {probe},{range_mode}")
    if num_inputs == 2:
        instr_b1500.write(f"RI {probe_b},{range_mode}")
    query_error(instr_b1500)

    # set output voltage measurement range mode
    range_mode_v = 50
    instr_b1500.write(f"RV {probe_out},{range_mode_v}")
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
    # standard staircase, these were valued used in past in stanford/mit
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


class ProgramKeysightCmosVoutVin(MeasurementProgram):
    """Implement CMOS logic Vout vs Vin DC voltage transfer sweep for
    configurable number of CMOS inputs (Va, Vb, ...) into a single Vout.
    """
    name = "keysight_cmos_vout_vin"

    def default_config_string() -> str:
        return """
            probe_a = 1
            probe_b = 2
            probe_out = 3
            probe_vdd = 4
            probe_vss = 5
            probe_sub = 9
            num_input = 1
            v_a = { start = 0, stop = 1.2, step = 0.1 }
            v_b = 0
            v_dd = 1.2
            v_ss = 0.0
            v_sub = 0.0
            negate_id = true
            sweep_direction = "fr"
        """

    def run(
        instr_b1500=None,
        monitor_channel: EventChannel = None,
        signal_cancel=None,
        sweep_metadata: dict = {},
        probe_a = 1,
        probe_b = 2,
        probe_out = 3,
        probe_vdd = 4,
        probe_vss = 5,
        probe_sub = 9,
        num_input = 1,
        v_a={
            "start": -1.2,
            "stop": 1.2,
            "step": 0.1,
        },
        v_b=0.0,
        v_dd = 1.2,
        v_ss = 0.0,
        v_sub = 0.0,
        sweep_direction="fr",
        id_compliance=0.010, # 10 mA drain complience
        ig_compliance=0.001, # 1 mA gate complience
        stop_on_error=True,
        yield_during_measurement=True,
        smu_slots={}, # map SMU number => actual slot number
        **kwargs,
    ) -> dict:
        """Run the program."""
        logging.info(f"probe_a = {probe_a}")
        logging.info(f"probe_b = {probe_b}")
        logging.info(f"probe_out = {probe_out}")
        logging.info(f"probe_vdd = {probe_vdd}")
        logging.info(f"probe_vss = {probe_vss}")
        logging.info(f"probe_sub = {probe_sub}")
        logging.info(f"v_a = {v_a}")
        logging.info(f"v_b = {v_b}")
        logging.info(f"v_dd = {v_dd}")
        logging.info(f"v_ss = {v_ss}")
        logging.info(f"v_sub = {v_sub}")
        logging.info(f"sweep_direction = {sweep_direction}")
        logging.info(f"id_compliance = {id_compliance}")
        logging.info(f"ig_compliance = {ig_compliance}")
        logging.info(f"smu_slots = {smu_slots}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_a = map_smu_to_slot(smu_slots, probe_a)
            probe_b = map_smu_to_slot(smu_slots, probe_b)
            probe_out = map_smu_to_slot(smu_slots, probe_out)
            probe_vdd = map_smu_to_slot(smu_slots, probe_vdd)
            probe_vss = map_smu_to_slot(smu_slots, probe_vss)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_a -> {probe_a}")
            logging.info(f"- probe_b -> {probe_b}")
            logging.info(f"- probe_out -> {probe_out}")
            logging.info(f"- probe_vdd -> {probe_vdd}")
            logging.info(f"- probe_vss -> {probe_vss}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check
        def query_error(instr_b1500):
            res = instr_b1500.query("ERRX?")
            if res[0:2] != "+0":
                logging.error(f"{res}")
                if stop_on_error:
                    raise RuntimeError(res)
        
        # non input probes (these use different compliance current id_compliance)
        probes_other = [probe_sub, probe_vdd, probe_vss, probe_out]

        # convert v_ds and v_gs into a list of values depending on variable object type
        v_a_range = into_sweep_range(v_a)
        v_b_range = into_sweep_range(v_b)

        # REMAP v_a and v_b to 'input_sweep' and 'input_const'
        # so that only one of these is swept and the other is constant
        # - verify ranges and ensure that only one input is swept (e.g. len > 0)
        # - choose longer vector as 'input_sweep' and the other as 'input_const'
        if num_input == 1:
            if len(v_a_range) <= 1:
                raise ValueError(f"Invalid v_a_range = {v_a_range}, must have more than one value")
            in_sweep, probe_sweep, v_sweep = "v_a", probe_a, v_a_range
            in_const, probe_const, v_const_values = "", None, [0.0] # fake sentinel for other inputs
            # list of all probe inputs
            probes_in = [probe_a]
        if num_input == 2:
            if len(v_a_range) <= 1 and len(v_b_range) <= 1:
                raise ValueError(f"Invalid v_a_range = {v_a_range} and v_b_range = {v_b_range}, must have more than one value")
            elif len(v_a_range) > 1 and len(v_b_range) > 1:
                raise ValueError(f"Invalid v_a_range = {v_a_range} and v_b_range = {v_b_range}, only one can be swept")
            # list of all probe inputs
            probes_in = [probe_a, probe_b]

            # choose longer vector as sweep
            if len(v_a_range) > len(v_b_range):
                in_sweep, probe_sweep, v_sweep = "v_a", probe_a, v_a_range
                in_const, probe_const, v_const_values = "v_b", probe_b, v_b_range
            else:
                in_sweep, probe_sweep, v_sweep = "v_b", probe_b, v_b_range
                in_const, probe_const, v_const_values = "v_a", probe_a, v_a_range
        else:
            raise ValueError(f"Invalid num_input = {num_input}, must be 1 or 2")
        
        # maps string of sweep directions like "frf" => list of [SweepType.FORWARD_REVERSE, SweepType.FORWARD]
        sweeps = SweepType.parse_string(sweep_direction)
        
        # prepare output data matrices
        num_sweeps = SweepType.count_total_num_sweeps(sweeps)
        num_points = len(v_sweep)
        num_const_points = len(v_const_values)
        data_shape = (num_const_points, num_sweeps, num_points)

        v_out_out = np.full(data_shape, np.nan)
        v_a_out = np.full(data_shape, np.nan)
        v_b_out = np.full(data_shape, np.nan)
        i_a_out = np.full(data_shape, np.nan)
        i_b_out = np.full(data_shape, np.nan)
        i_dd_out = np.full(data_shape, np.nan)
        i_ss_out = np.full(data_shape, np.nan)
        # timestamps
        time_v_out = np.full(data_shape, np.nan)
        time_i_dd_out = np.full(data_shape, np.nan)
        time_i_ss_out = np.full(data_shape, np.nan)

        # measurement compliance derived settings
        pow_compliance = 2 * abs(id_compliance * np.max(np.abs(v_a_range))) # power compliance [W]
        
        # standard keysight initialization for IV measurements
        measurement_keysight_b1500_setup_cmos(
            instr_b1500=instr_b1500,
            query_error=query_error,
            probe_a=probe_a,
            probe_b=probe_b,
            probe_out=probe_out,
            probe_vdd=probe_vdd,
            probe_vss=probe_vss,
            probe_sub=probe_sub,
            id_compliance=id_compliance,
            ig_compliance=ig_compliance,
            pow_compliance=pow_compliance,
        )

        # ===========================================================
        # PERFORM SWEEP FOR EACH VDS AND SWEEP DIRECTION
        # ===========================================================

        # sweep state
        t_run_avg = None  # avg program step time
        cancelled = False # flag for program cancelled before done

        for idx_in_const, v_in_const in enumerate(v_const_values):
            # round to mV
            v_in_const = round(v_in_const, 3)

            for idx_dir, sweep_type in SweepType.iter_with_sweep_index(sweeps):
                print(f"==============================")
                print(f"Measuring step (vin1 = {v_in_const} V)...")
                print(f"------------------------------")
                
                # select regular held staircase or pulsed staircase
                sweep_command = sweep_type.b1500_wv_sweep_command

                # write voltage staircase waveform
                wv_range_mode = 0 # AUTO
                cmd = sweep_command(
                    ch=probe_sweep,
                    range=wv_range_mode,
                    start=v_sweep[0],
                    stop=v_sweep[-1],
                    steps=num_points,
                    icomp=id_compliance,
                    pcomp=None, # can trigger false errors?
                )

                instr_b1500.write(cmd)

                query_error(instr_b1500)
                
                # write bulk, vdd, vss
                instr_b1500.write(f"DV {probe_sub},0,{v_sub},{id_compliance}")
                instr_b1500.write(f"DV {probe_vdd},0,{v_dd},{id_compliance}")
                instr_b1500.write(f"DV {probe_vss},0,{v_ss},{id_compliance}")
                query_error(instr_b1500)
                
                # write other constant input bias
                if num_input == 2:
                    instr_b1500.write(f"DV {probe_const},0,{v_in_const},{ig_compliance}")
                    query_error(instr_b1500)
                
                # execute and wait for data response
                instr_b1500.write("XE")

                # starting time for step
                t_start = time()

                # yield green thread during measurement to let other tasks run
                if yield_during_measurement and t_run_avg is not None and t_run_avg > 0:
                    t_sleep = 0.9 * t_run_avg
                    logging.info(f"[ProgramKeysightCmosVoutVin] SLEEPING: gevent.sleep({t_sleep:.3f})")
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
                for probe in probes_other:
                    instr_b1500.write(f"DV {probe},0,0,{id_compliance}")
                for probe in probes_in:
                    instr_b1500.write(f"DV {probe},0,0,{ig_compliance}")
                query_error(instr_b1500)
                
                # number of bytes in output data buffer
                nbytes = int(instr_b1500.query("NUB?"))
                print(f"nbytes={nbytes}")
                buf = instr_b1500.read()
                print(buf)

                # parse vals strings into numbers
                vals = buf.strip().split(",")
                vals = parse_keysight_str_values(vals)

                # values chunked for each measurement point:
                #   [ [vout, i_dd, i_ss, ig_a, ig_b, v_in0] , [vout, i_dd, i_ss, ig_a, ig_b, v_in0] , ... ]
                val_chunks = [ x for x in iter_chunks(vals, 11) ]
                print(val_chunks)

                # split val chunks into forward/reverse sweep components:
                if sweep_type == SweepType.FORWARD or sweep_type == SweepType.REVERSE:
                    sweep_chunks = [val_chunks]
                elif sweep_type == SweepType.FORWARD_REVERSE or sweep_type == SweepType.REVERSE_FORWARD:
                    sweep_chunks = [val_chunks[0:num_points], val_chunks[num_points:]]
                
                # indices for each val (note values come as pair 't,value')
                idx_v_out = 1
                idx_i_dd = 3
                idx_i_ss = 5
                idx_i_a = 7
                if num_input == 2:
                    idx_i_b = 9
                    idx_v_sweep = 10
                else:
                    idx_v_sweep = 8
                
                val_table = [] # values to print out to console for display

                for s, sweep_vals in enumerate(sweep_chunks):
                    for i, vals_chunk in enumerate(sweep_vals):
                        val_table.append([v_dd, v_ss, v_a, v_b, vals_chunk[idx_v_out], vals_chunk[idx_i_dd], vals_chunk[idx_i_ss], vals_chunk[idx_i_a], vals_chunk[idx_i_b]])

                        v_out_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_v_out]
                        i_dd_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_dd]
                        i_ss_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_ss]
                        v_a_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_v_sweep] if in_sweep == "v_a" else v_in_const
                        i_a_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_a]
                        if num_input == 2:
                            v_b_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_v_sweep] if in_sweep == "v_b" else v_in_const
                            i_b_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_b]
                        # timestamps
                        time_v_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_v_out-1]
                        time_i_dd_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_dd-1]
                        time_i_dd_out[idx_in_const, idx_dir + s, i] = vals_chunk[idx_i_ss-1]
                
                print(tabulate(val_table, headers=["v_dd [V]", "v_ss [V]", "v_a [V]", "v_b [V]", "v_out [V]", "i_dd [A]", "i_ss [A]", "i_ga [A]", "i_gb [A]"]))

                print("------------------------------")
                print(f"Finished step (vin1 = {v_in_const} V")
                print("==============================")

            # after each bias completes, send partial update
            if monitor_channel is not None and idx_in_const < num_const_points-1: # don't publish last step
                def task_update_program_status():
                    """Update program status."""
                    data={
                        "inputs": num_input,
                        "in_sweep": in_sweep,
                        "in_const": in_const,
                        "v_dd": v_dd,
                        "v_ss": v_ss,
                        "v_sub": v_sub,
                        "v_out": v_out_out,
                        "i_dd": np.abs(i_dd_out), # abs for easier plotting
                        "i_ss": np.abs(i_ss_out), # abs for easier plotting
                        "time_v_out": time_v_out,
                        "time_i_dd": time_i_dd_out,
                        "time_i_ss": time_i_ss_out,
                        "v_a": v_a_out,
                        "i_a": np.abs(i_a_out), # abs for easier plotting
                    }
                    if num_input == 2:
                        data["v_b"] = v_b_out
                        data["i_a"] = i_b_out
                    data_cleaned = dict_np_array_to_json_array(data) # converts np ndarrays to regular lists and replace nan

                    monitor_channel.publish({
                        "metadata": {
                            "program": ProgramKeysightCmosVoutVin.name,
                            "config": sweep_metadata,
                            "step": idx_in_const,
                            "step_total": num_const_points,
                        },
                        "data": data_cleaned,
                    })
                    
                gevent.spawn(task_update_program_status)

            # break after bias finished if cancelled
            if signal_cancel is not None and signal_cancel.is_cancelled():
                logging.info(f"[ProgramKeysightCmosVoutVin] CANCELLING PROGRAM")
                cancelled = True
                break
        
        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        data_out = {
            "inputs": num_input,
            "in_sweep": in_sweep,
            "in_const": in_const,
            "v_dd": v_dd,
            "v_ss": v_ss,
            "v_sub": v_sub,
            "v_out": v_out_out,
            "i_dd": i_dd_out,
            "i_ss": i_ss_out,
            "time_v_out": time_v_out,
            "time_i_dd": time_i_dd_out,
            "time_i_ss": time_i_ss_out,
            "v_a": v_a_out,
            "i_a": i_a_out,
        }
        if num_input == 2:
            data_out["v_b"] = v_b_out
            data_out["i_b"] = i_b_out

        return MeasurementResult(
            cancelled=cancelled,
            save_data=True, # save partial data even if cancelled
            data=data_out,
        )



if __name__ == "__main__":
    """
    Tests running the programs as standalone command-line module.
    """
    import argparse
    import os
    import json
    import pyvisa
    from controller.util.io import export_hdf5, export_mat
    from controller.backend import ControllerSettings

    parser = argparse.ArgumentParser(description="Run FET IV measurement.")

    parser.add_argument(
        "inputs",
        default=1,
        type=int,
        help="Number of inputs, either 1 or 2"
    )

    args = parser.parse_args()

    inputs = args.inputs

    if inputs != 1 or inputs != 2:
        print("Invalid number of CMOS logic inputs, must be 1 or 2")
        parser.print_help()
        exit()

    rm = pyvisa.ResourceManager()
    print(rm.list_resources())

    if len(rm.list_resources()) == 0:
        print("NO INSTRUMENTS FOUND")
        exit()
    
    # TODO: configure this shit

    # try to load default settings from "./settings/config.json"
    path_config = os.path.join("settings", "config.json")
    if os.path.exists(path_config):
        with open(path_config, "r") as f:
            config = ControllerSettings(**json.load(f))
    else:
        config = ControllerSettings() # default
    
    print(f"CONFIG = {config}")
    instr_b1500 = rm.open_resource(
        f"GPIB0::{config.gpib_b1500}::INSTR",
        # read_termination="\n", # default, not needed
        # write_termination="\n",
    )

    print(instr_b1500.query("*IDN?"))
    instr_b1500.write("*RST")

    def run_measurement():
        try:
            result = ProgramKeysightCmosVoutVin.run(
                instr_b1500=instr_b1500,
                smu_slots=config.smu_slots,
            )
            # print(result)
        except Exception as err:
            print(f"Measurement FAILED: {err}")
            instr_b1500.write(f"DZ") # ensure channels are zero-d
            print(traceback.format_exc())
        
        path_result_mat = f"debug/{ProgramKeysightCmosVoutVin.name}.mat"
        path_result_h5 = f"debug/{ProgramKeysightCmosVoutVin.name}.h5"
        export_hdf5(path_result_h5, result.data)
        export_mat(path_result_mat, result.data)
    
    task = gevent.spawn(run_measurement)
    gevent.joinall([task])

    # done, turn off
    print("MEASUREMENT DONE, TURNING OFF SMUs WITH CL")
    instr_b1500.write("CL")
