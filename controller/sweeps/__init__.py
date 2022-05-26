"""
Define interface for measurement sweeps.
"""
import logging
from abc import ABC, abstractmethod

# list of available sweep types (hardcoded)
MEASUREMENT_SWEEPS = [
    "array",
    "single",
]

def get_measurement_sweep(name):
    """Return sweep by name."""
    s = name.lower()
    if s == "array":
        from controller.sweeps import ArraySweep
        return ArraySweep
    elif s == "single":
        from controller.sweeps import SingleSweep
        return SingleSweep
    else:
        logging.error(f"Unknown sweep type: {name}")
        return None


class MeasurementSweep(ABC):
    """Interface for measurement sweeps."""
    
    @abstractmethod
    def run():
        """Run the sweep."""
        pass