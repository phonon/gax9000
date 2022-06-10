"""
Miscellaneous utils here
"""
import datetime
from multiprocessing.sharedctypes import Value

from numpy import Infinity

def iter_chunks(lst, size):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def timestamp(format="%Y_%m_%d_%H_%M_%S"):
    """Return detailed timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)

def timestamp_date(format="%Y_%m_%d"):
    """Return coarse date timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)

def into_sweep_range(v) -> list:
    """Convert different measurement value sweep formats into standard
    list of sweep values. Conversions are:
    - num -> [num]: single number to a list with 1 value
    - list -> list: for a list input, simply return same
    - {"start": x0, "stop": x1, "step": dx} -> [x0, x0 + dx, ..., x1]
        Convert a standard dict with "start", "stop", and "step" keys into
        a linspace.
    """
    if isinstance(v, float) or isinstance(v, int):
        return [v]
    elif isinstance(v, list):
        return v
    elif isinstance(v, dict):
        import numpy as np
        # abs required to ensure no negative points if stop < start
        # round required due to float precision errors, avoids .9999 npoint values
        npoints = 1 + int(abs(round((v["stop"] - v["start"])/v["step"])))
        return np.linspace(v["start"], v["stop"], npoints, dtype=np.float64)
    else:
        raise ValueError(f"Sweep range is an invalid format: {v}")

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

def parse_keysight_str_values(vals: list) -> list:
    """Parse a list of keysight ascii string measurement values
    into list of float values. This strips variable names from values
    so caller must know what each index corresponds to.
    
    Typically values look like:
        ['NCT+5.55189E+00', 'NCI+0.00005E-09', 'NAT+5.66104E+00', 'NAI+0.00000E-09',
        'NHT+5.77022E+00', 'NHI+0.00010E-09', 'WHV-1.20000E+00', 'NCT+5.83624E+00',
        'NCI+0.00000E-09', 'NAT+5.85902E+00', 'NAI+0.00000E-09', 'NHT+5.96819E+00',
        'NHI+0.00015E-09', 'WHV-1.10000E+00', 'NCT+6.03426E+00', 'NCI+0.00000E-09',
        'NAT+6.05703E+00', 'NAI+0.00010E-09', 'NHT+6.16623E+00', 'NHI+0.00000E-09',...]
    """
    nums = []
    for s in vals:
        # find first occurance of + or - in str
        idx = None
        for i in range(0, len(s)):
            if s[i] == "+" or s[i] == "-":
                idx = i
                break
        if idx is None:
            raise ValueError(f"Invalid value string in `parse_keysight_str_values`, could not find + or - in {s}")
        
        # parse to float
        # print(f"{s} => {s[idx:]} => {float(s[idx:])}")
        nums.append(float(s[idx:]))

    return nums