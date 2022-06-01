import traceback
from dis import Instruction
from enum import Enum, auto
from multiprocessing.sharedctypes import Value
import numpy as np
import gevent
import pyvisa
import logging
from controller.programs import MeasurementProgram

def query_error(
    instr_b1500,
):
    res = instr_b1500.query("ERRX?")
    if res[0:2] != "+0":
        raise RuntimeError(res)

class ProgramKeysightIdVds(MeasurementProgram):
    """Implement Id-Vds sweep with constant Vgs biases.
    The Id-Vds measurement is a staircase sweep (pg 2-8).
    The Vgs is stepped at a constant bias on each step,
    while Vds is sweeped in a staircase:
    
       Vds
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

    name = "keysight_id_vds"

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
            "v_ds": {
                "start": 0.0,
                "stop": 2.0,
                "step": 0.1,
            },
            "v_sub": 0.0,
            "negate_id": False,
            "sweep_direction": "fr",
        }
    
    def run(
        instr_b1500=None,
        probe_gate=8,
        probe_source=1,
        probe_drain=3,
        probe_sub=9,
        v_gs=np.array([0.050, 1.2]),
        v_ds=np.arange(-1.2, 1.2, 0.1),
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

        return {
            
        }


if __name__ == "__main__":
    """Tests running the program
    """
    
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
            ProgramKeysightIdVds.run(
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

