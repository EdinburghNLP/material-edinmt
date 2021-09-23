#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
r"""
NOTE: Other packages import globals from here, so be careful to avoid an 
import cycle by trying to import one of those subpackages here. 
"""
import os
import logging
import sys

from edinmt.configs.config import Config, TestConfig, is_truthy

def setup_logger(
        name='edinmt', 
        folder=None, 
        level=logging.DEBUG, 
        to_stdout=True
    ):
    r"""Write logs to the file at folder/name.log. Default folder is cwd."""
    if folder is None:
        folder = os.getcwd()
    os.makedirs(folder, exist_ok=True)
    fp = os.path.join(folder, name + '.log')

    logger = logging.getLogger(name)
    logger.setLevel(level)

    #delay is a half-fix for mem leak: https://bugs.python.org/issue23010
    file_handler = logging.FileHandler(fp, delay=True) 
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('[%(asctime)s:%(levelname)s:%(name)s:%(lineno)d] %(message)s')
    file_handler.setFormatter(file_formatter)

    stream_handler = None
    if to_stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_formatter = logging.Formatter('[%(levelname)s:%(name)s:%(lineno)d] %(message)s')
        stream_handler.setFormatter(stream_formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        if to_stdout:
            logger.addHandler(stream_handler)

    return logger


# SETUP THE CONFIG AND LOGGER THAT WILL BE USED IN OTHER MODULES
# NOTE: do this NOT in main because we run this on import (not as main)
if is_truthy(os.getenv('DEBUG', False)):
    CONFIG = TestConfig
else:
    CONFIG = Config
LOGGER = setup_logger(name="edinmt", level=CONFIG.LOG_LEVEL, to_stdout=True)

