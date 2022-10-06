import traceback
from dis import Instruction
from multiprocessing.sharedctypes import Value
import numpy as np
import gevent
import pyvisa
import logging
from tabulate import tabulate
from controller.programs import MeasurementProgram, MeasurementResult, SweepType
from controller.util import into_sweep_range, parse_keysight_str_values, iter_chunks, map_smu_to_slot


def query_error(
    instr_b1500,
):
    res = instr_b1500.query("ERRX?")
    if res[0:2] != "+0":
        raise RuntimeError(res)

class RramSweepConfig():
    """RRAM sweep bias configuration. Contain gate/drain/source"""
    def __init__(
        self,
        name,
        v_g,
        v_sweep,
    ):
        self.name = name
        self.v_g = v_g
        self.v_sweep = v_sweep
        self.num_points = len(v_sweep)

class ProgramKeysightRram1T1R(MeasurementProgram):
    """Implement 1T1R rram measurement.
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
    name = "keysight_rram_1t1r"

    def default_config():
        """Return default `run` arguments config as a dict."""
        return {
            "probe_gate": 1,
            "probe_source": 2,
            "probe_drain": 3,
            "probe_sub": 9,
            "v_form": 3.0,
            "v_set": 2.0,
            "v_reset": -2.0,
            "v_sub": 0.0,
            "v_g_form": 1.0,
            "v_g_set": 1.0,
            "v_g_reset": 1.0,
            "v_step": 0.1,
            "i_compliance_form": 1e-3,
            "i_compliance_set": 1e-3,
            "i_compliance_reset": 1e-3,
            "sequence": "fsr",
        }

    def run(
        instr_b1500=None,
        probe_gate=1,
        probe_source=4,
        probe_drain=8,
        probe_sub=9,
        v_form=3.0,
        v_set=2.0,
        v_reset=-2.0,
        v_sub=0.0,
        v_g_form=1.0,             # FET gate voltage when forming 
        v_g_set=1.0,              # FET gate voltage when setting
        v_g_reset=1.0,            # FET gate voltage when resetting
        v_step=0.1,               # voltage step during sweeps
        i_compliance_form=1e-3,   # ideally compliance should never hit (transistor should prevent)
        i_compliance_set=1e-3,
        i_compliance_reset=1e-3,
        sequence="frs",
        stop_on_error=True,
        smu_slots={}, # map SMU number => actual slot number
    ) -> dict:
        """Run the program."""
        print(f"probe_gate = {probe_gate}")
        print(f"probe_source = {probe_source}")
        print(f"probe_drain = {probe_drain}")
        print(f"probe_sub = {probe_sub}")
        print(f"v_form = {v_form}")
        print(f"v_set = {v_set}")
        print(f"v_reset = {v_reset}")
        print(f"v_sub = {v_sub}")
        print(f"v_g_form = {v_g_form}")
        print(f"v_g_set = {v_g_set}")
        print(f"v_g_reset = {v_g_reset}")
        print(f"i_compliance_form = {i_compliance_form}")
        print(f"i_compliance_set = {i_compliance_set}")
        print(f"i_compliance_reset = {i_compliance_reset}")
        print(f"sequence = {sequence}")
        
        if instr_b1500 is None:
            raise ValueError("Invalid instrument b1500 is None")
        
        # map smu probes to instrument slots
        if len(smu_slots) > 0:
            probe_gate = map_smu_to_slot(smu_slots, probe_gate)
            probe_source = map_smu_to_slot(smu_slots, probe_source)
            probe_drain = map_smu_to_slot(smu_slots, probe_drain)
            probe_sub = map_smu_to_slot(smu_slots, probe_sub)
            logging.info("Mapped SMU to slot:")
            logging.info(f"- probe_gate -> {probe_gate}")
            logging.info(f"- probe_source -> {probe_source}")
            logging.info(f"- probe_drain -> {probe_drain}")
            logging.info(f"- probe_sub -> {probe_sub}")

        # error check function
        def query_error(instr_b1500):
            res = instr_b1500.query("ERRX?")
            if res[0:2] != "+0":
                logging.error(f"{res}")
                if stop_on_error:
                    raise RuntimeError(res)
        
        # convert v_ds and v_gs into a list of values depending on variable object type
        v_form_range = into_sweep_range({"start": 0, "stop": v_form, "step": v_step})
        v_set_range = into_sweep_range({"start": 0, "stop": v_set, "step": v_step})
        v_reset_range = into_sweep_range({"start": 0, "stop": v_reset, "step": v_step})

        # parse sequence into bias configs
        num_sweeps_form = 0
        num_sweeps_reset = 0
        num_sweeps_set = 0
        bias_configs = []
        for i in range(len(sequence)):
            pattern = sequence[i]
            if pattern == "f": # form
                bias_configs.append(RramSweepConfig(name="form", v_g=v_g_form, v_sweep=v_form_range))
                num_sweeps_form += 1
            elif pattern == "s": # set
                bias_configs.append(RramSweepConfig(name="set", v_g=v_g_set, v_sweep=v_set_range))
                num_sweeps_set += 1
            elif pattern == "r": # reset
                bias_configs.append(RramSweepConfig(name="reset", v_g=v_g_reset, v_sweep=v_reset_range))
                num_sweeps_reset += 1
            else:
                raise ValueError(f"Invalid sweep pattern: {pattern}")
        
        # prepare output data matrices
        num_points_form = len(v_form_range)
        num_points_reset = len(v_reset_range)
        num_points_set = len(v_set_range)

        # always a forward and reverse sweep!
        num_directions = 2

        data_shape_form = (num_sweeps_form, num_directions, num_points_form)
        data_shape_reset = (num_sweeps_reset, num_directions, num_points_reset)
        data_shape_set = (num_sweeps_set, num_directions, num_points_set)
        
        # create separate dict data banks for form, set, and reset sweeps
        data_form = {
            "v_d": np.full(data_shape_form, np.nan),
            "v_g": np.full(data_shape_form, np.nan),
            "i_d": np.full(data_shape_form, np.nan),
            "i_s": np.full(data_shape_form, np.nan),
            "i_g": np.full(data_shape_form, np.nan),
            "time_i_d": np.full(data_shape_form, np.nan), # timestamp
            "time_i_s": np.full(data_shape_form, np.nan),
            "time_i_g": np.full(data_shape_form, np.nan),
        }

        data_reset = {
            "v_d": np.full(data_shape_reset, np.nan),
            "v_g": np.full(data_shape_reset, np.nan),
            "i_d": np.full(data_shape_reset, np.nan),
            "i_s": np.full(data_shape_reset, np.nan),
            "i_g": np.full(data_shape_reset, np.nan),
            "time_i_d": np.full(data_shape_reset, np.nan), # timestamp
            "time_i_s": np.full(data_shape_reset, np.nan),
            "time_i_g": np.full(data_shape_reset, np.nan),
        }

        data_set = {
            "v_d": np.full(data_shape_set, np.nan),
            "v_g": np.full(data_shape_set, np.nan),
            "i_d": np.full(data_shape_set, np.nan),
            "i_s": np.full(data_shape_set, np.nan),
            "i_g": np.full(data_shape_set, np.nan),
            "time_i_d": np.full(data_shape_set, np.nan), # timestamp
            "time_i_s": np.full(data_shape_set, np.nan),
            "time_i_g": np.full(data_shape_set, np.nan),
        }

        # measurement compliance settings
        id_compliance = 0.100 # 100 mA complience
        ig_compliance = 0.010 # 10 mA complience
        pow_compliance = abs(id_compliance * np.max(v_form_range)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        instr_b1500.query("ERRX?") # clear any existing error message and ignore

        # enable channels: CN (pg 4-62)
        instr_b1500.write(f"CN {probe_sub},{probe_gate},{probe_drain},{probe_source}")
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
        instr_b1500.write(f"AAD {probe_drain},{adc_type}")
        instr_b1500.write(f"AAD {probe_source},{adc_type}")
        instr_b1500.write(f"AAD {probe_gate},{adc_type}")
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
        instr_b1500.write(f"DV {probe_gate},0,0,{ig_compliance}")
        instr_b1500.write(f"DV {probe_sub},0,0,{id_compliance}")
        instr_b1500.write(f"DV {probe_drain},0,0,{id_compliance}")
        instr_b1500.write(f"DV {probe_source},0,0,{id_compliance}")
        query_error(instr_b1500)

        # set measurement mode to multi-channel staircase sweep (MODE = 16) (4-151, pg 471):
        #   MM mode,ch0,ch1,ch2,...
        mm_mode = 16
        instr_b1500.write(f"MM {mm_mode},{probe_drain},{probe_source},{probe_gate}");
        query_error(instr_b1500)

        # set probe current measurement mode (4-62, pg 382):
        #   CMM ch,mode
        CMM_MODE_COMPLIANCE = 0
        CMM_MODE_CURRENT = 1
        CMM_MODE_VOLTAGE = 2
        CMM_MODE_FORCE = 3
        CMM_MODE_SYNC = 4
        cmm_mode = CMM_MODE_CURRENT
        instr_b1500.write(f"CMM {probe_drain},{cmm_mode}")
        instr_b1500.write(f"CMM {probe_source},{cmm_mode}")
        instr_b1500.write(f"CMM {probe_gate},{cmm_mode}")
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
        instr_b1500.write(f"RI {probe_source},{range_mode}")
        instr_b1500.write(f"RI {probe_drain},{range_mode}")
        instr_b1500.write(f"RI {probe_gate},{range_mode}")
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

        # track current index in each sweep type
        idx_form = 0
        idx_reset = 0
        idx_set = 0

        # output data dict index. set to either
        # idx_form, idx_reset, or idx_set
        idx_data = 0

        # ===========================================================
        # PERFORM SWEEP FOR EACH VDS AND SWEEP DIRECTION
        # ===========================================================

        # sweep state
        t_run_avg = None  # avg program step time
        cancelled = False # flag for program cancelled before done

        for i, sweep in enumerate(bias_configs):
            # unpack sweep config
            v_g = sweep.v_g
            v_sweep = sweep.v_sweep
            num_points = sweep.num_points
            
            # print(f"v_g = {v_g}")
            # print(f"v_sweep = {v_sweep}")
            # print(f"num_points = {num_points}")

            # select output data dict
            if sweep.name == "form":
                data_out = data_form
                idx_data = idx_form
                idx_form += 1
            elif sweep.name == "reset":
                data_out = data_reset
                idx_data = idx_reset
                idx_reset += 1
            elif sweep.name == "set":
                data_out = data_set
                idx_data = idx_set
                idx_set += 1
            else:
                raise ValueError("Invalid output data dict!")

            print(f"============================================================")
            print(f"Measuring step {i}: {sweep.name} @ V = {v_sweep[-1]}")
            print(f"------------------------------------------------------------")
            
            # write voltage staircase waveform
            wv_range_mode = 0 # AUTO
            wv_cmd = SweepType.FORWARD_REVERSE.b1500_wv_sweep_command(
                ch=probe_drain,
                range=wv_range_mode,
                start=v_sweep[0],
                stop=v_sweep[-1],
                steps=num_points,
                icomp=id_compliance,
                pcomp=None, # ignore for now
            )
            # print(wv_cmd)
            instr_b1500.write(wv_cmd)
            query_error(instr_b1500)
            
            # write gate bias
            instr_b1500.write(f"DV {probe_gate},0,{v_g},{ig_compliance}")
            query_error(instr_b1500)
            
            # write bulk bias
            instr_b1500.write(f"DV {probe_sub},0,{v_sub},{id_compliance}")
            query_error(instr_b1500)
            
            # execute and wait for data response
            instr_b1500.write("XE")

            # set timeout (milliseconds)
            instr_b1500.timeout = 60 * 1000
            _opc = instr_b1500.query("*OPC?")
            instr_b1500.timeout = 10 * 1000
            query_error(instr_b1500)
            
            # zero probes after measurement
            instr_b1500.write(f"DV {probe_gate},0,0,{ig_compliance}")
            instr_b1500.write(f"DV {probe_sub},0,0,{id_compliance}")
            instr_b1500.write(f"DV {probe_drain},0,0,{id_compliance}")
            instr_b1500.write(f"DV {probe_source},0,0,{id_compliance}")
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
                    
                    data_out["v_d"][idx_data, s, i] = vals_chunk[6]
                    data_out["v_g"][idx_data, s, i] = v_g
                    data_out["i_d"][idx_data, s, i] = vals_chunk[1]
                    data_out["i_s"][idx_data, s, i] = vals_chunk[3]
                    data_out["i_g"][idx_data, s, i] = vals_chunk[5]
                    # timestamps
                    data_out["time_i_d"][idx_data, s, i] = vals_chunk[0]
                    data_out["time_i_s"][idx_data, s, i] = vals_chunk[2]
                    data_out["time_i_g"][idx_data, s, i] = vals_chunk[4]
            
            print(tabulate(val_table, headers=["v_g [V]", "v_d [V]", "i_d [A]", "i_s [A]", "i_g [A]"]))

            print("============================================================")

        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        # merge data dicts
        data_dict = {}
        for k, v in data_form.items():
            data_dict[f"form_{k}"] = v
        for k, v in data_reset.items():
            data_dict[f"reset_{k}"] = v
        for k, v in data_set.items():
            data_dict[f"set_{k}"] = v

        return MeasurementResult(
            cancelled=cancelled,
            data=data_dict,
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
                probe_gate=1,
                probe_source=4,
                probe_drain=8,
                v_form=2.0,
                v_set=1.5,
                v_reset=-2.0,
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