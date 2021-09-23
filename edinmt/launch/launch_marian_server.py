#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
r"""
Run an instance of the marian-server with settings set up from
existing environment variables.
"""
import argparse
import asyncio
import inspect
import logging
import multiprocessing
import os
import subprocess
import sys
import websockets
from subprocess import PIPE
from typing import *

import yaml

from edinmt import CONFIG
from edinmt.get_settings import get_decoder_settings 

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.launch.launch_marian_server')
logger.setLevel(CONFIG.LOG_LEVEL)

def launch(extra_args=None):
    r"""Parse arguments from configs, and start the marian-server."""
    port = CONFIG.MARIAN_PORT

    #get the list of args we need to send the marian server
    #(don't need batch_size/n_best/config since it's already in extra_args)
    decoder_settings = get_decoder_settings(
        extra_args=extra_args, config=CONFIG, server=True)

    decoder_settings.cmd.append('--port')
    decoder_settings.cmd.append(f'{port}')

    logger.info(f"RUNNING: {' '.join(decoder_settings.cmd)}")
    pi = subprocess.Popen(decoder_settings.cmd, stdout=PIPE, stderr=sys.stderr)
    pi.wait()


def parse_args():
    r"""Parse command line args for launch_marian_server.py"""
    parser = argparse.ArgumentParser(
        description="launch marian-server running the requested system",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    #most settings should be parsed through environment variables in
    #the config, but we use the argparser to help us push through
    #any additional marian args directly to the marian-server
    args, rest = parser.parse_known_args()
    args.rest = rest
    return args

if __name__ == "__main__":
    args = parse_args()
    print(f'Launching marian-server with args: {args}...')
    launch(extra_args=args.rest)