#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
r"""
Translate a text on stdin to stdout.

NOTE: Arguments are read from the environment variable configurations, but
some additional arguments are exposed to the user on the command line, so
that they have an option of how to invoke the system at runtime.
See edinmt.get_settings for where we read and override environment variables.
"""
import argparse
import logging
import os
import subprocess

from edinmt import CONFIG
from edinmt.get_settings import get_decoder_settings
from edinmt.translate_input import translate 

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.translate_input')
logger.setLevel(CONFIG.LOG_LEVEL)

def main(
        src_lang, 
        tgt_lang, 
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
        src_lang: source language (required for text pre/post text_processors)
        tgt_lang: source language (required for text pre/post text_processors)
        system_name: name of the system directory in the SYSTEMS_DIR
        use_mode: "fast" for single model, "accurate" for ensemble
        n_best: True to output n-best sentences (n is set from model settings)
        n_best_words: True to output n-best tokens in each position
        fmt: output json-lines format instead of plain text
        marian_args: extra marian args passed directly to marian-decoder

    Side-effects:
        writes translations to stdout

    #NOTE: This will search for the marian-decoder and other settings. To run
    #outside of the Docker system, set the environment variables in 
    #edinmt.configs.config.Config correctly, in particular: 
    # - MARIAN_BUILD_DIR
    # - SYSTEMS_DIR 
    """
    user_settings = {'SRC': src_lang, 'TGT': tgt_lang} 
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

    logger.debug(f"RUNNING: {' '.join(decoder_settings.cmd)}")
    translate(
        subcommand=decoder_settings.cmd,
        text_processor=decoder_settings.text_processor, 
        batch_size=decoder_settings.batch_size, 
        n_best=decoder_settings.n_best,
        n_best_words=decoder_settings.n_best_words,
        extract_tags=decoder_settings.extract_tags,
        fmt=decoder_settings.fmt,
    )

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, 
        description="Translate input from stdin to stdout, using the marian-decoder.",
    )
    parser.add_argument('src_lang', help='source language')
    parser.add_argument('tgt_lang', help='target language')
    parser.add_argument('--system', default=CONFIG.SYSTEM, 
        help='determines which included system to use')
    parser.add_argument('--mode', default=CONFIG.MODE, choices=["fast", "accurate"],
        help='determines which marian config to use')
    parser.add_argument('--n-best', default=CONFIG.NBEST, action="store_true",
        help='return n-best sentences instead of 1 best (n will be determined by model settings)')
    parser.add_argument('--n-best-words', default=CONFIG.NBEST_WORDS, action="store_true",
        help='return the n-best tokens for each position (n will be determined by model settings)')
    parser.add_argument('--fmt', default=CONFIG.FMT, choices=CONFIG.FMTS,
        help='output json-lines, marian format (with |||) or plain text')
    args, rest = parser.parse_known_args()
    args.rest = rest

    return args

if __name__ == '__main__':
    args = parse_args()
    main(
        src_lang=args.src_lang, 
        tgt_lang=args.tgt_lang, 
        use_mode=args.mode,
        n_best=args.n_best,
        n_best_words=args.n_best_words,
        fmt=args.fmt, 
        marian_args=args.rest
    )