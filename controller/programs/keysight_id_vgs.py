from controller.programs import MeasurementProgram

class ProgramKeysightIdVgs(MeasurementProgram):
    """Implement Id-Vgs sweep with constant Vds biases."""
    
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
            "v_ds": [-0.05, -0.4, -1.2],
        }
    
    def run(self):
        """Run the program."""
        pass