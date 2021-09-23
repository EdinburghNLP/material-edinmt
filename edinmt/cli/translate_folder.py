#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
r"""
Translate a folder of text files into an output folder with the same directory
structure.

NOTE: Arguments are read from the environment variable configurations, but
some additional arguments are exposed to the user on the command line, so
that they have an option of how to invoke the system at runtime.
See edinmt.get_settings for where we read and override environment variables.
"""
import argparse
import logging
import os
import subprocess
import sys
from typing import *

from edinmt import CONFIG
from edinmt.get_settings import get_decoder_settings
from edinmt.translate_folder import translate

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.translate_folder')
logger.setLevel(CONFIG.LOG_LEVEL)

def main(
        src_lang, 
        tgt_lang, 
        input_dir, 
        output_dir,
        systems_dir=None,
        system_name=None, 
        use_mode=None, 
        n_best=None,
        n_best_words=None,
        fmt=None, 
        marian_args=None
    ):
    r"""
    Run the translation pipeline (which invokes marian-decoder) to
    translate from stdin to stdout.

    Args:
        src_lang: source language (required for text pre/post text processors)
        tgt_lang: source language (required for text pre/post text processors)
        input_dir: directory with source language files
        output_dir: directory to save translations (the same directory 
            structure as input_dir will be created for you)
        system_name: name of the system directory in the SYSTEMS_DIR
        fmt: output json-lines format instead of plain text
        use_mode: "fast" for single model, "accurate" for ensemble
        marian_args: extra marian args passed directly to marian-decoder

    Side-effects:
        creates the output_dir with translations 

    #NOTE: This will search for the marian-decoder and other settings. To run
    #outside of the Docker system, set at least these envuronment variables:
    # - MARIAN_BUILD_DIR
    # - SYSTEMS_DIR 
    """
    user_settings = {'SRC': src_lang, 'TGT': tgt_lang} 
    if systems_dir is not None:
        user_settings['SYSTEMS_DIR'] = systems_dir
    if system_name is not None:
        user_settings['SYSTEM'] = system_name
    if use_mode is not None:
        user_settings['MODE'] = use_mode
    if n_best is not None:
        user_settings['NBEST'] = n_best
    if n_best_words is not None:
        user_settings['NBEST_WORDS'] = n_best_words
    if fmt is not None:
        user_settings['FMT'] = fmt

    decoder_settings = get_decoder_settings(
        src_lang, tgt_lang, user_settings=user_settings, extra_args=marian_args
    )

    returncode = translate(
        subcommand=decoder_settings.cmd,
        input_dir=input_dir,
        output_dir=output_dir,
        text_processor=decoder_settings.text_processor, 
        n_best=decoder_settings.n_best, 
        n_best_words=decoder_settings.n_best_words,
        fmt=decoder_settings.fmt,
        extract_tags=decoder_settings.extract_tags,
        purge=CONFIG.PURGE
    )
    return returncode

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, 
        description="Translate a folder of files into output files following the same directory structure, using the marian-decoder.",
    )
    parser.add_argument('src_lang', help='source language')
    parser.add_argument('tgt_lang', help='target language')
    parser.add_argument('input_dir', 
        help="a folder consisting of input files to the command (all files in the directory will be processed)")
    parser.add_argument('output_dir', 
        help="the output directory where to save new files")
    parser.add_argument('--systems_dir', default=CONFIG.SYSTEMS_DIR,
        help='the folder where all the systems are located')
    parser.add_argument('--system', default=CONFIG.SYSTEM,
        help='determines which included system to use')
    parser.add_argument('--mode', default=CONFIG.MODE, choices=["fast", "accurate"], 
        help='determines which marian config to use')
    parser.add_argument('--n-best', default=CONFIG.NBEST, action="store_true",
        help='return n-best sentences instead of 1 best (n will be determined by model settings)')
    parser.add_argument('--n-best-words', default=CONFIG.NBEST_WORDS, action="store_true",
        help='return the n-best tokens for each position (n will be determined by model settings)')
    parser.add_argument('--fmt', default=CONFIG.FMT, choices=CONFIG.FMTS,
        help='output plain text instead of json-lines')
    args, rest = parser.parse_known_args()
    args.rest = rest

    if not os.path.exists(args.input_dir):
        raise FileNotFoundError(f"Folder not found: {args.input_dir}")
    if not os.path.isdir(args.input_dir):
        raise NotADirectoryError(f"File is not a directory: {args.input_dir}")

    return args


if __name__ == '__main__':
    args = parse_args()
    main(
        src_lang=args.src_lang, 
        tgt_lang=args.tgt_lang, 
        input_dir=args.input_dir, 
        output_dir=args.output_dir, 
        systems_dir=args.systems_dir,
        system_name=args.system,
        use_mode=args.mode,
        n_best=args.n_best,
        n_best_words=args.n_best_words, 
        fmt=args.fmt, 
        marian_args=args.rest
    )