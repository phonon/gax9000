"""
Data import/export utilities.
"""

import os
import h5py
from scipy.io import savemat
import numpy as np


def export_hdf5(path: str, data: dict):
    """Export all keys in dict to hdf5 datasets, and save hdf5 file.
    """
    with h5py.File(path, "w") as h5:
        for k, val in data.items():
            h5.create_dataset(k, data=val)

def export_mat(path: str, data: dict):
    """Wrapper around scipy saving matlab .mat file"""
    savemat(path, data, appendmat=False)
