"""
Data import/export utilities.
"""

import os
import h5py
from scipy.io import savemat, loadmat
import numpy as np


def export_hdf5(path: str, data: dict):
    """Export all keys in dict to hdf5 datasets, and save hdf5 file.
    """
    with h5py.File(path, "w") as h5:
        for k, val in data.items():
            h5.create_dataset(k, data=val)

def import_hdf5(path):
    """Import device id-vg datasets in an hdf5 file
    into an EasyDict
    """
    d = {}

    with h5py.File(path, "r") as h5:
        for k in h5.keys():
            if len(h5[k].shape) > 0:
                d[k] = h5[k][:]
            else:
                d[k] = np.asscalar(h5[k][()])

    return d


def export_mat(path: str, data: dict):
    """Wrapper around scipy saving matlab .mat file"""
    savemat(path, data, appendmat=False)

def import_mat(path):
    """Wrapper around scipy loadmat"""
    return loadmat(path)
