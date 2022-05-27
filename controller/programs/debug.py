import gevent
import numpy as np
from controller.programs import MeasurementProgram

class ProgramDebug(MeasurementProgram):
    """Implement fake debugging program."""

    def run(
        **kwargs
    ):
        """Run the program."""
        print("RUNNING DEBUG PROGRAM")

        # simulate running
        gevent.sleep(2)
        
        v_gs = np.arange(10)
        v_ds = np.full(v_gs.shape, 0.05)
        i_d = 1e-6 * v_gs
        i_g = 1e-9 * v_gs

        return {
            "v_ds": v_ds,
            "v_gs": v_gs,
            "i_d": i_d,
            "i_g": i_g,
        }