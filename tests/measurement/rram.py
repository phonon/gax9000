"""
Tests for RRAM 1T1R measurement program.
"""

import unittest
import numpy as np
from controller.programs.keysight_rram_1t1r import ProgramKeysightRram1T1R, ProgramKeysightRram1T1RSweep, ProgramKeysightRram1T1RSequence

def print_bias_configs(bias_configs):
    for i, bias_config in enumerate(bias_configs):
        print(f"[{i}] [{bias_config.name}]: v_sub={bias_config.v_sub:.3f}, v_s={bias_config.v_s:.3f}, v_g={bias_config.v_g:.3f}, v_d={bias_config.v_d_sweep[-1]:.3f}")

class TestRram(unittest.TestCase):
    def test_sweep_sequence_bias_configs(self):
        bias_configs, num_points_max = ProgramKeysightRram1T1RSweep.parse_sweep_sequence(
            v_sub=0,
            v_s=0,
            v_g_reset=-1.0,
            v_d_reset=-2.0,
            v_g_range=[0.4, 0.6, 0.8],
            v_d_range=[1.0, 1.5, 2.5],
            v_step=0.1,
        )
        print(f"[ProgramKeysightRram1T1RSweep] num_points_max={num_points_max}")
        print_bias_configs(bias_configs)
    
    def test_code_sequence_bias_configs(self):
        config = ProgramKeysightRram1T1RSequence.default_config()
        bias_configs, num_points_max = ProgramKeysightRram1T1RSequence.parse_sweep_sequence(
            codes=config["codes"],
            sequence=config["sequence"],
            v_step=0.1,
        )
        print(f"[ProgramKeysightRram1T1RSequence] codes={config['codes']}")
        print(f"[ProgramKeysightRram1T1RSequence] sequence={config['sequence']}")
        print(f"[ProgramKeysightRram1T1RSequence] num_points_max={num_points_max}")
        print_bias_configs(bias_configs)

if __name__ == '__main__':
    unittest.main()