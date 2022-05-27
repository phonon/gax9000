"""
Define interface for measurement programs on B1500.
"""
import logging
from abc import ABC, abstractmethod

# list of available program names (hardcoded)
MEASUREMENT_PROGRAMS = [
    "debug",
    "keysight_id_vds",
    "keysight_id_vgs",
]

def get_measurement_program(name):
    """Return sweep by name."""
    s = name.lower()
    if s == "debug":
        from controller.programs.debug import ProgramDebug
        return ProgramDebug
    elif s == "keysight_id_vds":
        from controller.programs.keysight_id_vds import ProgramKeysightIdVds
        return ProgramKeysightIdVds
    elif s == "keysight_id_vgs":
        from controller.programs.keysight_id_vgs import ProgramKeysightIdVgs
        return ProgramKeysightIdVgs
    else:
        logging.error(f"Unknown program type: {name}")
        return None


class MeasurementProgram(ABC):
    """Interface for measurement programs."""
    
    @staticmethod
    @abstractmethod
    def run(**kwargs):
        """Run the program."""
        pass
