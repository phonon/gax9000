"""
Script for taking remote die photographs in Cascade system using GPIB.
Support both taking single images or doing an array of images and
auto-stitching to create a die photo. 
"""

import pyvisa
import os
import time
import shutil
import tomli

# Example configuration toml for taking images. Contains paths and calibration
# settings specific to each cascade controller.
SAMPLE_CONFIG_TOML = \
"""
# instrument address on gpib network
gpib_address = "GPIB0::22::INSTR"

# paths where images are stored on the tool, accessed using the
# institution network remote file system access.
# (make sure paths are single quoted, so backslash not escaped)
path_to_img_dir_on_network = '\\\\GAX1-PROBE\shared\gax_tmp_img'
path_to_img_dir_local = 'D:\shared\gax_tmp_img'

# size of output images in pixels
img_size_x = 1024
img_size_y = 768

# user-defined image zoom levels and calibrations.
# names and pixels/um at each zoom level (must be calculated)
[calibration.1]
name = "eVue1"
pixels_per_um = 0.465 # 465 px / 1000 um

[calibration.2]
name = "eVue2"
pixels_per_um = 1.7667 # 530 px / 300 um

[calibration.3]
name = "eVue3"
pixels_per_um = 4.48 # 448 px / 100 um
"""

def timestamp(format="%Y_%m_%d_%H_%M_%S"):
    """Return detailed timestamp string"""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)

def connect_to_cascade(addr: str):
    """Connect and return gpib object for cascade instrument controller."""
    gpib_resource_manager = pyvisa.ResourceManager()
    instrument_cascade = gpib_resource_manager.open_resource(config["gpib_address"])
    print(instrument_cascade.query("*IDN?"))
    return instrument_cascade

def gpib_cmd_snap_image(zoom: str, path_to_img: str):
    """Return cascade GPIB command to snap image."""
    return f"SnapImage {zoom} {path_to_img}"

def move_image_from_remote_when_ready(
    path_remote: str,
    path_out: str,
    poll_timeout = 0.5, # timeout between poll checks
    timeout = 30.0,     # max allowed before error 30s
):
    """Issue is there is no way to query when image is ready after
    sending the GPIB command. So instead rely on polling to check
    if image is done. When done, move it from remote file system to
    desired output path.

    From testing, it can take 8-10s for image to be ready and appear, so
    polling is done by default at coarse 0.5s intervals.
    """
    tstart = time.perf_counter()

    while True:
        # print(f"POLLING ({time.perf_counter() - tstart})")
        if os.path.exists(path_remote):
            shutil.move(path_remote, path_out)
            return
        else:
            dt = time.perf_counter() - tstart
            if dt > timeout:
                raise RuntimeError(f"Failed to get output image in time {path_remote} (timeout: {timeout})")
            time.sleep(poll_timeout)


def take_die_photo(
    config: dict,
    zoom: str,
    size_x: int,
    size_y: int,
    path_out: str,
    format: str = "png",
):
    """Do a sweep to get a die photo over input x, y size range"""
    instrument_cascade = connect_to_cascade(config["gpib_address"])
    
    # calculate um used per image. insert 10% margin in images (e.g. stitch 
    # with 10% overlap between images)
    # TODO


def take_image(
    config: dict,
    zoom: str,
    path_out: str,
    format: str = "png",
):
    """Take single image snapshot and save to output directory."""
    instrument_cascade = connect_to_cascade(config["gpib_address"])

    path_to_img_dir_on_network = config["path_to_img_dir_on_network"]
    path_to_img_dir_local = config["path_to_img_dir_local"]

    print(f"path_to_img_on_network: {path_to_img_dir_on_network}")
    print(f"path_to_img_local: {path_to_img_dir_local}")

    img_name = f"snapshot_zoom_{zoom}.{format}"
    img_raw_name = f"snapshot_zoom_{zoom}_raw.{format}" # raw image has no labels

    path_to_img = os.path.join(path_to_img_dir_local, img_name)
    cmd_snap_image = gpib_cmd_snap_image(config["calibration"][zoom]["name"], path_to_img)

    instrument_cascade.write(cmd_snap_image)
    instrument_cascade.read() # read required to flush response
    instrument_cascade.query("*OPC?")
    instrument_cascade.close()

    # copy image to local output
    path_img_remote = os.path.join(path_to_img_dir_on_network, img_name)
    path_img_out = os.path.join(path_out, img_name)
    path_img_remote_raw = os.path.join(path_to_img_dir_on_network, img_raw_name)
    path_img_out_raw = os.path.join(path_out, img_raw_name)
    move_image_from_remote_when_ready(path_img_remote, path_img_out)
    move_image_from_remote_when_ready(path_img_remote_raw, path_img_out_raw)
    print(f"Saved image to: {path_img_out}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Merge RRAM 1T1R sequence measurement files into single .h5 file.")

    parser.add_argument(
        "-c",
        "--config",
        metavar="config",
        type=str,
        help="Path to instrument config/calibration"
    )
    parser.add_argument(
        "-p",
        "--path_out",
        metavar="path_out",
        dest="path_out",
        type=str,
        default="scripts/test",
        help="Path to put image output"
    )
    parser.add_argument(
        "-z",
        "--zoom",
        metavar="zoom",
        dest="zoom",
        type=str,
        default="1",
        help="Zoom level for snapshot"
    )
    parser.add_argument(
        "-x",
        metavar="um",
        dest="size_x",
        type=int,
        help="Total x size in [um] (for creating panorama)"
    )
    parser.add_argument(
        "-y",
        metavar="um",
        dest="size_y",
        type=int,
        help="Total y size in [um] (for creating panorama)"
    )

    args = parser.parse_args()

    print(args)
    
    if args.config is not None:
        with open(args.config, "rb") as f:
            config = tomli.load(f)
    else:
        print("No config file specified...using sample config settings")
        config = tomli.loads(SAMPLE_CONFIG_TOML)
    
    print(config)

    zoom = args.zoom
    if zoom is None or zoom not in config["calibration"]:
        zoom_settings = config["calibration"]
        raise ValueError(f"Invalid zoom setting: {zoom}, must be one of {list(zoom_settings.keys())}")

    # if x, y arguments specified, take a panorama
    x = args.size_x
    y = args.size_y
    if x is None and y is None: # take single image
        take_image(config, zoom, args.path_out)
    else:
        if x is None or y is None: # must both be specified
            raise ValueError(f"For taking panorama, must specify both -x and -y: currently x: {x}, y: {y}")
        
        take_die_photo(
            config=config,
            zoom=zoom,
            size_x=x,
            size_y=y,
            path_out=args.path_out,
        )
