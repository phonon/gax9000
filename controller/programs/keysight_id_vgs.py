import traceback
from dis import Instruction
from multiprocessing.sharedctypes import Value
import numpy as np
import gevent
import pyvisa
import logging
from tabulate import tabulate
from controller.programs import MeasurementProgram, SweepType
from controller.util import into_sweep_range, parse_keysight_str_values, iter_chunks


def query_error(
    instr_b1500,
):
    res = instr_b1500.query("ERRX?")
    if res[0:2] != "+0":
        raise RuntimeError(res)

class ProgramKeysightIdVgs(MeasurementProgram):
    """Implement Id-Vgs sweep with constant Vds biases.
    The Id-Vgs measurement is a staircase sweep (pg 2-8).
    The Vds is stepped at a constant bias on each step,
    while Vgs is sweeped in a staircase:
    
       Vgs
        |          Measurement points
        |            |   |   |   |
        |            v   v   v   v
        |WV                     ___
        |                   ___/   \    
        |   XE          ___/        \  
        |____       ___/             \ 
        |    \_____/                  \___
        |_____________________________________ time
    
    """
    name = "keysight_id_vgs"

    def default_config():
        """Return default `run` arguments config as a dict."""
        return {
            "probe_gate": 8,
            "probe_source": 1,
            "probe_drain": 3,
            "probe_sub": 9,
            "v_gs": {
                "start": -1.2,
                "stop": 1.2,
                "step": 0.1,
            },
            "v_ds": [-0.05, -1.2],
        }

    def run(
        instr_b1500,
        probe_gate=8,
        probe_source=1,
        probe_drain=3,
        probe_sub=9,
        v_gs={
            "start": -1.2,
            "stop": 1.2,
            "step": 0.1
        },
        v_ds=[0.050, 1.2],
        v_sub=0.0,
        negate_id=False,
        sweep_direction="fr",
    ) -> dict:
        """Run the program."""
        print(f"probe_gate = {probe_gate}")
        print(f"probe_source = {probe_source}")
        print(f"probe_gate = {probe_gate}")
        print(f"probe_sub = {probe_sub}")
        print(f"v_ds = {v_ds}")
        print(f"v_gs = {v_gs}")
        print(f"negate_id = {negate_id}")
        print(f"sweep_direction = {sweep_direction}")

        # convert v_ds and v_gs into a list of values depending
        v_gs_range = into_sweep_range(v_gs)
        v_ds_range = into_sweep_range(v_ds)

        # maps string of sweep directions like "frf" => list of [SweepType.FORWARD_REVERSE, SweepType.FORWARD]
        sweeps = SweepType.parse_string(sweep_direction)
        
        # prepare output data matrices
        num_bias = len(v_ds_range)
        num_sweeps = SweepType.count_total_num_sweeps(sweeps)
        num_points = len(v_gs_range)
        data_shape = (num_bias, num_sweeps, num_points)

        v_ds_out = np.full(data_shape, np.nan)
        v_gs_out = np.full(data_shape, np.nan)
        i_d_out = np.full(data_shape, np.nan)
        i_s_out = np.full(data_shape, np.nan)
        i_g_out = np.full(data_shape, np.nan)
        # timestamps
        time_i_d_out = np.full(data_shape, np.nan)
        time_i_s_out = np.full(data_shape, np.nan)
        time_i_g_out = np.full(data_shape, np.nan)

        # measurement compliance settings
        id_compliance = 0.100 # 100 mA complience
        ig_compliance = 0.010 # 10 mA complience
        pow_compliance = abs(id_compliance * np.max(v_ds)) # power compliance [W]

        # reset instrument
        instr_b1500.write("*RST")
        
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
        
        # ===========================================================
        # PERFORM SWEEP FOR EACH VDS AND SWEEP DIRECTION
        # ===========================================================
        for idx_bias, v_ds_val in enumerate(v_ds_range):
            for idx_dir, sweep_type in SweepType.iter_with_sweep_index(sweeps):
                print(f"==============================")
                print(f"Measuring step (Vds = {v_ds_val} V)...")
                print(f"------------------------------")
                
                # write voltage staircase waveform
                wv_range_mode = 0 # AUTO
                instr_b1500.write(sweep_type.b1500_wv_sweep_command(
                    ch=probe_gate,
                    range=wv_range_mode,
                    start=v_gs_range[0],
                    stop=v_gs_range[-1],
                    steps=len(v_gs_range),
                    icomp=id_compliance,
                    pcomp=pow_compliance,
                ))
                query_error(instr_b1500)
                
                # write drain bias
                instr_b1500.write(f"DV {probe_drain},0,{v_ds_val},{id_compliance}")
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
                print(buf)
                vals = buf.strip().split(",")
                vals = parse_keysight_str_values(vals)
                print(vals)

                val_table = []
                for i, vals_chunk in enumerate(iter_chunks(vals, 7)):
                    val_table.append([v_ds_val, vals_chunk[6], vals_chunk[1], vals_chunk[3], vals_chunk[5]])
                    
                    v_ds_out[idx_bias, idx_dir, i] = v_ds_val
                    v_gs_out[idx_bias, idx_dir, i] = vals_chunk[6]
                    i_d_out[idx_bias, idx_dir, i] = vals_chunk[1]
                    i_s_out[idx_bias, idx_dir, i] = vals_chunk[3]
                    i_g_out[idx_bias, idx_dir, i] = vals_chunk[5]
                    # timestamps
                    time_i_d_out[idx_bias, idx_dir, i] = vals_chunk[0]
                    time_i_s_out[idx_bias, idx_dir, i] = vals_chunk[2]
                    time_i_g_out[idx_bias, idx_dir, i] = vals_chunk[4]
                
                print(tabulate(val_table, headers=["v_ds [V]", "v_gs [V]", "i_d [A]", "i_s [A]", "i_g [A]"]))

                print("------------------------------")
                print(f"Measuring step (Vds = {v_ds_val} V")
                print("==============================")

        # zero voltages: DZ (pg 4-79)
        # The DZ command stores the settings (V/I output values, V/I output ranges, V/I
        # compliance values, and so on) and sets channels to 0 voltage.
        instr_b1500.write(f"DZ")

        return {
            "v_ds": v_ds_out,
            "v_gs": v_gs_out,
            "i_d": i_d_out,
            "i_s": i_s_out,
            "i_g": i_g_out,
            "time_i_d": time_i_d_out,
            "time_i_s": time_i_s_out,
            "time_i_g": time_i_g_out,
        }



if __name__ == "__main__":
    """Tests running the program
    """
    res = "NCT+5.55189E+00,NCI+0.00005E-09,NAT+5.66104E+00,NAI+0.00000E-09,NHT+5.77022E+00,NHI+0.00010E-09,WHV-1.20000E+00,NCT+5.83624E+00,NCI+0.00000E-09,NAT+5.85902E+00,NAI+0.00000E-09,NHT+5.96819E+00,NHI+0.00015E-09,WHV-1.10000E+00,NCT+6.03426E+00,NCI+0.00000E-09,NAT+6.05703E+00,NAI+0.00010E-09,NHT+6.16623E+00,NHI+0.00000E-09,WHV-1.00000E+00,NCT+6.23234E+00,NCI+0.00000E-09,NAT+6.25518E+00,NAI+0.00000E-09,NHT+6.36435E+00,NHI+0.00010E-09,WHV-0.90000E+00,NCT+6.43042E+00,NCI+0.00005E-09,NAT+6.45328E+00,NAI+0.00005E-09,NHT+6.56246E+00,NHI+0.00005E-09,WHV-0.80000E+00,NCT+6.62855E+00,NCI+0.00015E-09,NAT+6.65140E+00,NAI+0.00005E-09,NHT+6.76060E+00,NHI+0.00010E-09,WHV-0.70000E+00,NCT+6.82667E+00,NCI+0.00000E-09,NAT+6.84944E+00,NAI+0.00000E-09,NHT+6.95864E+00,NHI+0.00015E-09,WHV-0.60000E+00,NCT+7.02471E+00,NCI+0.00010E-09,NAT+7.04756E+00,NAI+0.00005E-09,NHT+7.15675E+00,NHI+0.00010E-09,WHV-0.50000E+00,NCT+7.22284E+00,NCI+0.00005E-09,NAT+7.24569E+00,NAI-0.00010E-09,NHT+7.35487E+00,NHI+0.00000E-09,WHV-0.40000E+00,NCT+7.42094E+00,NCI+0.00010E-09,NAT+7.44379E+00,NAI+0.00015E-09,NHT+7.55299E+00,NHI+0.00010E-09,WHV-0.30000E+00,NCT+7.61906E+00,NCI+0.00005E-09,NAT+7.64190E+00,NAI+0.00010E-09,NHT+7.75107E+00,NHI+0.00015E-09,WHV-0.20000E+00,NCT+7.81712E+00,NCI+0.00000E-09,NAT+7.83997E+00,NAI+0.00010E-09,NHT+7.94907E+00,NHI+0.00005E-09,WHV-0.10000E+00,NCT+8.01521E+00,NCI+0.00000E-09,NAT+8.03806E+00,NAI+0.00010E-09,NHT+8.14722E+00,NHI+0.00015E-09,WHV+0.00000E+00,NCT+8.21331E+00,NCI+0.00000E-09,NAT+8.23608E+00,NAI-0.00005E-09,NHT+8.34523E+00,NHI+0.00000E-09,WHV+0.10000E+00,NCT+8.41130E+00,NCI+0.00000E-09,NAT+8.43407E+00,NAI+0.00010E-09,NHT+8.54324E+00,NHI+0.00015E-09,WHV+0.20000E+00,NCT+8.60933E+00,NCI+0.00000E-09,NAT+8.63209E+00,NAI+0.00015E-09,NHT+8.74126E+00,NHI+0.00015E-09,WHV+0.30000E+00,NCT+8.80730E+00,NCI+0.00000E-09,NAT+8.83016E+00,NAI+0.00005E-09,NHT+8.93933E+00,NHI+0.00010E-09,WHV+0.40000E+00,NCT+9.00542E+00,NCI+0.00010E-09,NAT+9.02826E+00,NAI+0.00000E-09,NHT+9.13741E+00,NHI+0.00015E-09,WHV+0.50000E+00,NCT+9.20348E+00,NCI+0.00000E-09,NAT+9.22632E+00,NAI+0.00010E-09,NHT+9.33545E+00,NHI+0.00005E-09,WHV+0.60000E+00,NCT+9.40154E+00,NCI+0.00000E-09,NAT+9.42431E+00,NAI+0.00000E-09,NHT+9.53348E+00,NHI+0.00010E-09,WHV+0.70000E+00,NCT+9.59954E+00,NCI-0.00005E-09,NAT+9.62241E+00,NAI+0.00010E-09,NHT+9.73154E+00,NHI+0.00000E-09,WHV+0.80000E+00,NCT+9.79756E+00,NCI+0.00010E-09,NAT+9.82043E+00,NAI+0.00005E-09,NHT+9.92957E+00,NHI+0.00015E-09,WHV+0.90000E+00,NCT+9.99564E+00,NCI+0.00010E-09,NAT+1.00184E+01,NAI+0.00015E-09,NHT+1.01276E+01,NHI+0.00000E-09,WHV+1.00000E+00,NCT+1.01936E+01,NCI+0.00005E-09,NAT+1.02165E+01,NAI+0.00015E-09,NHT+1.03256E+01,NHI+0.00015E-09,WHV+1.10000E+00,NCT+1.03917E+01,NCI+0.00000E-09,NAT+1.04145E+01,NAI+0.00005E-09,NHT+1.05236E+01,NHI+0.00005E-09,EHV+1.20000E+00"
    print(res)
    vals = res.strip().split(",")
    vals = parse_keysight_str_values(vals)
    print(vals)

    val_table = []
    for vals_chunk in iter_chunks(vals, 7):
        print(vals_chunk)
        val_table.append(["0.05", vals_chunk[6], vals_chunk[1], vals_chunk[3], vals_chunk[5]])
    
    print(tabulate(val_table, headers=["v_ds [V]", "v_gs [V]", "i_d [A]", "i_s [A]", "i_g [A]"]))

    exit()

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
            ProgramKeysightIdVgs.run(
                instr_b1500=instr_b1500,
            )
        except Exception as err:
            print(f"Measurement FAILED: {err}")
            instr_b1500.write(f"DZ") # ensure channels are zero-d
            print(traceback.format_exc())

        
    task = gevent.spawn(run_measurement)
    gevent.joinall([task])

    # done, turn off
    print("MEASUREMENT DONE, TURNING OFF SMUs WITH CL")
    instr_b1500.write("CL")
    query_error(instr_b1500)