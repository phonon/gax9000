"""
Miscellaneous utils here
"""
import datetime

def timestamp(format="%Y_%m_%d_%H_%M_%S"):
    """Return detailed timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)

def timestamp_date(format="%Y_%m_%d"):
    """Return coarse date timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)


def np_dict_to_list_dict(d: dict) -> list:
    """Convert dict of numpy ndarrays dict to list of dicts"""
    import numpy as np
    x = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray):
            x[k] = v.tolist()
        else:
            x[k] = v
    return x