"""
Define interface for measurement programs on B1500.
"""
import logging
from abc import ABC, abstractmethod

# list of available program names (hardcoded)
MEASUREMENT_PROGRAMS = [
    "keysight_id_vds",
    "keysight_id_vgs",
]

def get_measurement_program(name):
    """Return sweep by name."""
    s = name.lower()
    if s == "keysight_id_vds":
        from controller.programs import ProgramKeysightIdVds
        return ProgramKeysightIdVds
    elif s == "keysight_id_vgs":
        from controller.programs import ProgramKeysightIdVgs
        return ProgramKeysightIdVgs
    else:
        logging.error(f"Unknown program type: {name}")
        return None

class MeasurementProgram(ABC):
    """Interface for measurement programs."""
    
    @abstractmethod
    def run(self):
        """Run the program."""
        pass
