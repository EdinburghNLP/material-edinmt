#!/usr/bin/env python3.7
r"""
Command line script to process files in an input directory and save the
results to an output directory with the same directory structure. Any
subprocess can be invoked on for processing the files.
"""
import argparse
import logging
import os
import subprocess
import sys
import threading
import queue
from typing import *
from typing import IO #the * above won't load this

logger = logging.getLogger(__name__)

def _mux(input_dir: str, process_stdin: IO, q: queue.Queue):
    r"""Write files in the input_dir to the stdin and track them in the q."""
    for (base, unused_dirs, files) in os.walk(input_dir):
        for file_name in files:
            name = os.path.join(base, file_name)
            with open(name, "rb") as f:
                count = 0
                for line in f:
                    process_stdin.write(line)
                    count += 1
            relative_name = os.path.relpath(name, input_dir)
            q.put((relative_name, count))
    q.put(None) #poison
    process_stdin.close()

def _demux(output_dir: str, process_stdout: IO, q: queue.Queue):
    r"""Read tracking from q and write stdout lines to files in output_dir."""
    while True:
        item = q.get()
        if item is None:
            break
        relative_name, count = item
        name = os.path.join(output_dir, relative_name)
        os.makedirs(os.path.dirname(name), exist_ok=True)
        with open(name, "wb") as out:
            for l in range(count):
                line = process_stdout.readline()
                out.write(line)
        q.task_done()

def mux_demux(input_dir: str, output_dir: str, process_stdin: IO, process_stdout: IO):
    r"""
    Read files in the input_dir, send them to process_stdin, receive results
    from process_stdout, and write the results to new files in the output_dir
    with the same directory structure.
    """
    q = queue.Queue()
    muxer = threading.Thread(target=_mux, args=(input_dir, process_stdin, q))
    demuxer = threading.Thread(target=_demux, args=(output_dir, process_stdout, q))
    muxer.start()
    demuxer.start()
    muxer.join()
    demuxer.join()

def main(input_dir: str, output_dir: str, subcommand: list):
    r"""
    Process a directory of files using a subprocess command.

    Args:
        input_dir: an input directory with files to process
        output_dir: a new output directory to save resulting files
        subcommand: the command to invoke as a subprocess

    Side-effects:
        creates an output_dir with the same directory structure as the
            input_dir, but with files processed by the subcommand
    """
    process = subprocess.Popen(subcommand, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
    mux_demux(input_dir, output_dir, process.stdin, process.stdout)
    sys.exit(process.wait())

def parse_args():
    r"""Parse command line args for process_folder.py"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, 
        description="Process a folder of files into output files following the same directory structure, using a shell subprocess.",
        epilog="Example usage: mux_demux.py ./input_dir ./output_dir ~/marian-dev/build/marian-decoder --devices 0 1"
    )
    parser.add_argument('input_dir', 
        help="a folder consisting of input files to the command (all files in the directory will be processed)")
    parser.add_argument('output_dir', 
        help="the output directory where to save new files")
    args, rest = parser.parse_known_args()
    args.rest = rest

    if not os.path.exists(args.input_dir):
        raise FileNotFoundError(f"Folder not found: {args.input_dir}")
    if not os.path.isdir(args.input_dir):
        raise NotADirectoryError(f"File is not a directory: {args.input_dir}")
    if not args.rest:
        raise BaseException(f"Process to invoke not provided.")

    return args

if __name__ == '__main__':
    args = parse_args()
    main(args.input_dir, args.output_dir, args.rest)

