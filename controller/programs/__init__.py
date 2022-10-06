"""
Define interface for measurement programs on B1500.
"""
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto

# list of available program names (hardcoded)
MEASUREMENT_PROGRAMS = [
    "debug",
    "debug_multistep",
    "keysight_id_vds",
    "keysight_id_vgs",
    "keysight_rram_1t1r",
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
            from controller.programs.keysight_id_vds import ProgramKeysightIdVds
            return ProgramKeysightIdVds
        elif s == "keysight_id_vgs":
            from controller.programs.keysight_id_vgs import ProgramKeysightIdVgs
            return ProgramKeysightIdVgs
        elif s == "keysight_rram_1t1r":
            from controller.programs.keysight_rram_1t1r import ProgramKeysightRram1T1R
            return ProgramKeysightRram1T1R
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
        - range: ranging type for staircase (Table 4-4)
        - start: start voltage
        - stop: stop voltage
        - steps: steps in staircase sweep
        - icomp: current compliance in [A]
        - pcomp: power compliance in [W], resolution 0.001 W

        The SweepType sets the mode for the sweep:
            1: linear sweep, single-stair start to stop
            2: log sweep, single-stair start to stop
            3: linear sweep, double-stair start to stop to start
            4: log sweep, double-stair, start to stop to start
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
    def iter_with_sweep_index(sweeps: list):
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