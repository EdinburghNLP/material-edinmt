#!/usr/bin/env python3.7
# -*- coding: utf-8 -*
r"""Utility functions used throughout edinmt."""
import logging
import os
import subprocess
import sys
from subprocess import PIPE, DEVNULL
from typing import *
from typing import IO #the * above doesn't get this one

import yaml

from edinmt import CONFIG

logger = logging.getLogger(__name__)
logger.setLevel(CONFIG.LOG_LEVEL)


def popen_communicate(cmd: list, text: str, suppress: Optional[bool]=True) -> str:
    r"""
    Send text to a subprocess through stdin and receive the response on stdout.

    Args:
        cmd: the command as a list, e.g. ["sh", "script.sh", "--flag", "arg"]
        text: the string to send as input to cmd
        suppress: suppress warnings from cmd and extra debug messages 

    Returns:
        text: a string of the stdout of the cmd
    """
    cmd = ' '.join(cmd)
    if not suppress:
        logger.debug(f"RUNNING: {cmd}")

    p = subprocess.Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = p.communicate(input=text.encode('utf-8'))

    if p.returncode != 0:
        raise BaseException(f"ERROR: {p.returncode}; {stderr.strip()}")
    elif stderr and len(stderr) and not suppress:
        logger.warning(stderr.strip())

    text = stdout.decode('utf-8')
    return text

def fix_broken_chars(fp: str, outfp: str) -> str:
    r"""
    Remove the null character, zero width space, and lonely carriage return.
    This is used to fix the line endings so parallel files actually align.
    """
    cmd = f'sed -e "s/\r//g" {fp} > {outfp}.tmp' #from windows line endings
    subprocess.check_output(cmd, shell=True)
    with open(outfp + '.tmp', 'r', encoding='utf-8') as infile, \
         open(outfp, 'w', encoding='utf-8') as outfile:
        for line in infile:
            line = line.replace('\x00', '') #null byte
            line = line.replace('\u200c', '') #zero width non joiner
            line = line.replace('\ufeff', '') #zero width non breaking space
            outfile.write(line)
    os.remove(outfp + '.tmp')
    return outfp

def get_file_length(filepath: str):
    r"""
    Run linux awk to count number of records (faster than doing it in python).

    NOTE: Use awk instead of wc because wc only counts \n, while awk counts
    records like other tools do, see: https://stackoverflow.com/a/35052861
    """
    out = subprocess.check_output(["awk", "END{print NR}", filepath])
    length = int(out.split()[0])
    return length

def get_git_revision_hash():
    r"""Get last git commit's revision hash number (for version tracking)."""
    return subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()

