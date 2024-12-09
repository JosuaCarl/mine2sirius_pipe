#!/usr/bin/env python
"""
Common helpers for tests
"""
import time
import platform as pf
import shutil
import source.helpers.general as helpers

from icecream import ic as ic
from tqdm import tqdm as tqdm

import pytest as pytest

def get_platform():
    return pf.system()

def contruct_common_paths( filepath ):
    out_path = helpers.construct_path(filepath, "..", "out")
    test_path = helpers.construct_path(filepath, "..", "test_files")
    example_path = helpers.construct_path(filepath, "..", "example_files")
    batch_path = helpers.construct_path(filepath, "..", "batch_files")
    
    return out_path, test_path, example_path, batch_path

def clean_out( out_path ):
    shutil.rmtree( out_path )
    helpers.make_new_dir( out_path )

def wait( counter:float, unit:str="s"):
    if unit == "s" or unit.startswith("second"):
        time.sleep( counter )
    elif unit == "m" or unit.startswith("min"):
        time.sleep( counter * 60 )
    elif unit == "h" or unit.startswith("hour"):
        time.sleep( counter * 60 * 60 )
    elif unit == "d" or unit.startswith("day"):
        time.sleep( counter * 60 * 60 * 24 )
    else:
        raise( ValueError(f"unit {unit} is invalid, please choose between d/h/m/s.") )
