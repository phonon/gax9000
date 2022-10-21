"""
Define interface for measurement programs on B1500.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Iterator, Tuple
# TODO: in future python 3.11, we can import "from typing import Self" for type hint


# list of available program names (hardcoded)
MEASUREMENT_PROGRAMS = [
    "debug",
    "debug_multistep",
    "keysight_id_vds",
    "keysight_id_vgs",
    "keysight_id_vds_pulsed_dc",
    "keysight_id_vgs_pulsed_dc",
    "keysight_rram_1t1r",
    "keysight_rram_1t1r_sweep",
    "keysight_rram_1t1r_sequence",
]

class MeasurementResult():
    """Wrapper for measurement result data and status flags."""
    def __init__(
        self,
        cancelled,
        data,
        save_data=None,
    ):
        self.cancelled = cancelled
        
        # by default, only save data if not cancelled
        # in some cases measurement program may want to override
        if save_data is not None:
            self.save_data = save_data
        else:
            self.save_data = not cancelled
        
        self.data = data

class MeasurementProgram(ABC):
    """Interface for measurement programs."""
    
    # program name, must match name in `get(name)`
    name = None

    @staticmethod
    @abstractmethod
    def default_config():
        """Return default `run` arguments config as a dict."""
        return {}

    @staticmethod
    @abstractmethod
    def run(**kwargs) -> MeasurementResult:
        """Run the program and returns MeasurementResult object with result
        data and measurement status flags. The result data is program
        specific and must be manually parsed by caller for different
        programs.
        
        The controller will inject built-in arguments that any program
        can optionally use:
        - `instr_b1500`: B1500 pyvisa instrument object
        - `monitor_channel`: EventChannel object for sending status updates
        - `signal_cancel`: SignalCancelTask object for checking for user cancel signal
        - `sweep_metadata`: Copy of sweep metadata dict
        """
        pass
    
    @staticmethod
    def get(name):
        """Return measurement program class by name."""
        s = name.lower()
        if s == "debug":
            from controller.programs.debug import ProgramDebug
            return ProgramDebug
        if s == "debug_multistep":
            from controller.programs.debug import ProgramDebugMultistep
            return ProgramDebugMultistep
        elif s == "keysight_id_vds":
            from controller.programs.keysight_fet_iv import ProgramKeysightIdVds
            return ProgramKeysightIdVds
        elif s == "keysight_id_vgs":
            from controller.programs.keysight_fet_iv import ProgramKeysightIdVgs
            return ProgramKeysightIdVgs
        elif s == "keysight_id_vds_pulsed_dc":
            from controller.programs.keysight_fet_iv import ProgramKeysightIdVdsPulsedDC
            return ProgramKeysightIdVdsPulsedDC
        elif s == "keysight_id_vgs_pulsed_dc":
            from controller.programs.keysight_fet_iv import ProgramKeysightIdVgsPulsedDC
            return ProgramKeysightIdVgsPulsedDC
        elif s == "keysight_rram_1t1r":
            from controller.programs.keysight_rram_1t1r import ProgramKeysightRram1T1R
            return ProgramKeysightRram1T1R
        elif s == "keysight_rram_1t1r_sweep":
            from controller.programs.keysight_rram_1t1r import ProgramKeysightRram1T1RSweep
            return ProgramKeysightRram1T1RSweep
        elif s == "keysight_rram_1t1r_sequence":
            from controller.programs.keysight_rram_1t1r import ProgramKeysightRram1T1RSequence
            return ProgramKeysightRram1T1RSequence
        else:
            logging.error(f"Unknown program type: {name}")
            return None


# TODO: map sweep_direction to this list
class SweepType(Enum):
    """SweepType enum maps a sweep direction to a sweep setting
    """
    FORWARD = auto()          # [start, stop]
    REVERSE = auto()          # [stop, start]
    FORWARD_REVERSE = auto()  # [start, stop, start]
    REVERSE_FORWARD = auto()  # [stop, start, stop]

    def b1500_wv_sweep_command(self, ch, range, start, stop, steps, icomp, pcomp=None):
        """This returns b1500 GPIB WV voltage sweep mode command (4-250, pg 570):
            WV ch,mode,range,start,stop,step[,Icomp[,Pcomp]]
        Parameters:
        - ch: SMU channel
        - mode: sweep mode (forward/rev/fwd-rev/rev-fwd), integer 1-4
        - range: ranging type for staircase (Table 4-4)
        - start: start voltage
        - stop: stop voltage
        - steps: number of steps in staircase sweep
        - icomp: current compliance in [A]
        - pcomp: power compliance in [W], resolution 0.001 W

        The SweepType sets the mode for the sweep:
            1: linear sweep, single-stair start to stop
            2: log sweep, single-stair start to stop
            3: linear sweep, double-stair start to stop to start
            4: log sweep, double-stair, start to stop to start
        
        As example:
        Each Id-Vgs measurement is a staircase sweep (pg 2-8).
        The Vds is stepped at a constant bias on each step,
        while Vgs is sweeped in a separate WV staircase measurement.
        
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
        pow_comp = f",{pcomp}" if pcomp is not None else ""

        if self == SweepType.FORWARD:
            mode = 1
            return f"WV {ch},{mode},{range},{start},{stop},{steps},{icomp}{pow_comp}"
        elif self == SweepType.REVERSE:
            mode = 1
            return f"WV {ch},{mode},{range},{stop},{start},{steps},{icomp}{pow_comp}"
        elif self == SweepType.FORWARD_REVERSE:
            mode = 3
            return f"WV {ch},{mode},{range},{start},{stop},{steps},{icomp}{pow_comp}"
        elif self == SweepType.REVERSE_FORWARD:
            mode = 3
            return f"WV {ch},{mode},{range},{stop},{start},{steps},{icomp}{pow_comp}"
        else:
            raise ValueError(f"Invalid SweepType: {self}")
    
    def b1500_mcpwnx_sweep_commands(self, ch, range, start, stop, steps, icomp, pcomp=None, base=0) -> list[str]:
        """
        This returns a list of MCPWS and a MCPWNX command. These are both 
        needed to run a multi-channel pulsed sweep measurement.
        
        MCPWNX: set sweep mode and number of steps
            MCPWS mode,step
        Parameters:
            mode : sweep mode (forward/rev/fwd-rev/rev-fwd), integer 1-4
                1: Linear sweep (single stair, start to stop.)
                2: Log sweep (single stair, start to stop.)
                3: Linear sweep (double stair, start to stop to start.)
                4: Log sweep (double stair, start to stop to start.)
            step : Number of sweep steps. Numeric expression. 1 to 10001.

        MCPWNX: pulsed staircase sweep (4-173, pg 493):
            MCPWNX N,ch,mode,range,base,start,stop[,comp[,Pcomp]]
        Parameters:
            N: source number, the N value and the chnum value set to the
                MCPNX, MCPWNX, and WNX commands must be unique for execution.
            ch: SMU channel
            mode: 1: voltage source, 2: current source
            range: ranging type for staircase (Table 4-4)
            base: base voltage (voltage floor between pulses)
            start: start voltage
            stop: stop voltage
            icomp: current compliance in [A]
            pcomp: power compliance in [W], resolution 0.001 W
        
        As example:
        Each Id-Vgs measurement is a pulse staircase sweep (2-12).
        The Vds is stepped at a constant bias on each step,
        while Vgs is sweeped in a separate PWV staircase measurement.
        
             Vgs
              |            Measurement points
              |             |       |       |
              |             |       |       v
              |WV           |       |     ___
              |             |       v    |   |
              |   XE        v     ___    |   |
              |____       ___    |   |   |   | 
        BASE _|    \_____|   |___|   |___|   |_____
          V   |_____________________________________ time

        Note: difference between this and WV command is that we need a "base voltage"
        parameter which is voltage LOW value floor between pulse HIGH values.
        """
        pow_comp = f",{pcomp}" if pcomp is not None else ""

        if self == SweepType.FORWARD:
            sweep_mode = 1
            sweep_start = start
            sweep_stop = stop
        elif self == SweepType.REVERSE:
            sweep_mode = 1
            sweep_start = stop
            sweep_stop = start
        elif self == SweepType.FORWARD_REVERSE:
            mode = 3
            sweep_mode = 3
            sweep_start = start
            sweep_stop = stop
        elif self == SweepType.REVERSE_FORWARD:
            sweep_mode = 3
            sweep_start = stop
            sweep_stop = start
        else:
            raise ValueError(f"Invalid SweepType: {self}")
        
        return [
            f"MCPWS {sweep_mode},{steps}",
            f"MCPWNX 1,{ch},1,{range},{base},{sweep_start},{sweep_stop},{icomp}{pow_comp}",
        ]

    @staticmethod
    def parse_string(s: str):
        """Maps string of sweep directions like "frf" into a list of SweepType:
            "frf" => [SweepType.FORWARD_REVERSE, SweepType.FORWARD]
        This must iterate through string and pattern match up to 2 characters
        on each step and match them to sweep type. B1500 only supports
        forward and forward-reverse style sweeps. So we will convert:
            f/r => forward/reverse "single stair" type sweep
            fr/rf => "double stair" type sweep
        """
        sweeps = []

        idx = 0
        slen = len(s)
        while idx < slen:
            print(f"idx={idx}, slen={slen}")
            if idx < slen-1: # match 2 chars
                pattern = s[idx:idx+2]
                if pattern == "ff":
                    sweeps.append(SweepType.FORWARD)
                    idx += 1
                elif pattern == "rr":
                    sweeps.append(SweepType.REVERSE)
                    idx += 1
                elif pattern == "fr":
                    sweeps.append(SweepType.FORWARD_REVERSE)
                    idx += 2
                elif pattern == "rf":
                    sweeps.append(SweepType.REVERSE_FORWARD)
                    idx += 2
                else:
                    raise ValueError(f"Invalid sweep pattern: {pattern}")
            else: # reached end: match 1 char
                pattern = s[idx]
                if pattern == "f":
                    sweeps.append(SweepType.FORWARD)
                    break
                elif pattern == "r":
                    sweeps.append(SweepType.REVERSE)
                    break
                else:
                    raise ValueError(f"Invalid sweep pattern: {pattern}")
        
        return sweeps
    
    @staticmethod
    def count_total_num_sweeps(sweeps: list) -> int:
        """Count total number of sweeps in a list of SweepType, where a single
        sweep direction `Forward` or `Reverse` counts as a single sweep.
        This means Forward-Reverse / Reverse-Forward count as 2 sweeps.
        """
        count = 0
        for s in sweeps:
            if s == SweepType.FORWARD or s == SweepType.REVERSE:
                count += 1
            elif s == SweepType.FORWARD_REVERSE or s == SweepType.REVERSE_FORWARD:
                count += 2
            else:
                raise ValueError(f"Invalid SweepType: {s}")
        return count
    
    @staticmethod
    def iter_with_sweep_index(sweeps: list) -> Iterator[Tuple[int, SweepType]]:
        """Create iterator that yields running sweep index,
        where ForwardReverse and ReverseForward iterate the index
        by 2 (since they are composed of two sweeps).
        """
        i = 0
        for s in sweeps:
            if s == SweepType.FORWARD or s == SweepType.REVERSE:
                yield (i, s) 
                i += 1
            elif s == SweepType.FORWARD_REVERSE or s == SweepType.REVERSE_FORWARD:
                yield (i, s)
                i += 2
            else:
                raise ValueError(f"Invalid SweepType: {s}")

if __name__ == "__main__":
    sweeps = SweepType.parse_string("frffr")
    print(sweeps, SweepType.count_total_num_sweeps(sweeps))

    for i, s in SweepType.iter_with_sweep_index(sweeps):
        print(i, s)