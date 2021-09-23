#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
"""
Translate a folder of utf-8 files. Preprocess the small files using
text preprocessors (e.g. clean, bpe, tokenize, truecase, etc.), combine 
them into a big file, translate the big file and write the output to a 
target file, parse the target file into chunks that correspond to the 
small files (parsing method depends on which decoder was used), 
postprocess the contents (e.g. debpe, detokenize, detruecase, etc.), 
and write them to small files using the same directory structure in 
the output dir as was in the input dir.
"""
import itertools
import json
import logging
import multiprocessing
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from functools import partial
from subprocess import PIPE
from typing import *
from typing import IO #the * doesn't get this

from tqdm import tqdm

from edinmt import CONFIG
from edinmt import retagger 
from edinmt.parse_marian import (
    parse, 
    parse_nbest_words, 
    unwrap_lines,
    fmt_item
)
from edinmt.text_processors.text_processors import TextProcessor
from edinmt.translate_file import (
    clean_file,
    process_file,
)
from edinmt.utils import get_file_length
from edinmt.parallely import pll_single

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger("edinmt.translate_folder")
logger.setLevel(CONFIG.LOG_LEVEL)

def cat_files(
        input_dir: str, 
        out_fp: str, 
        suffix: Optional[str]='.input'
    ) -> list:
    r"""
    Concatenate the files in the input dir with the suffix into one output
    file. Return the ordered list of files that went into the big file.
    """
    #use find to get the same ordering of files that we'll use in cat below
    cmd = f'find {input_dir} -name "*{suffix}"'
    logger.debug(f"RUNNING FILE LIST: {cmd}")
    result = subprocess.check_output(cmd, shell=True)
    result = result.decode('utf-8').strip()
    ordered_files = []
    if result:
        ordered_files = [i for i in result.split('\n')]
    #concat (this avoids Argument list too long bash error for too many files)
    cmd = f'find {input_dir} -name "*{suffix}" | xargs cat > {out_fp}'
    logger.debug(f"RUNNING CONCAT: {cmd}")
    subprocess.check_output(cmd, shell=True)
    logger.debug(f"Found {len(ordered_files)} files to concat: {ordered_files}.")
    return ordered_files

def prepare_file(input_fp, input_dir, output_dir, suffix='.rdy', extract_tags=False):
    r"""
    Clean spurrious \r from the input_fp, and save it to the output_dir
    in the same relative name + suffix as the original had inside the 
    main input_dir creating subdirs when needed. If the retagger was
    used, also save an additional file with tag replacement metadata.

    Returns:
        created_fp, tags_fp, relative_name, length
    """
    relative_name = os.path.relpath(input_fp, input_dir)
    ready_fp = os.path.join(output_dir, relative_name) + suffix 
    tmp_fp = os.path.join(output_dir, relative_name + '.tmp')
    os.makedirs(os.path.dirname(ready_fp), exist_ok=True)

    tmp_fp = clean_file(input_fp, tmp_fp + '.clean')

    tags_fp = None
    if extract_tags:
        tags_fp = tmp_fp + '.repls'
        protected_fp = tmp_fp + '.tag_protected'
        tmp_fp, tags_fp = retagger.extract_tags_file(tmp_fp, protected_fp, tags_fp)

    shutil.move(tmp_fp, ready_fp)
    length = get_file_length(ready_fp)

    return ready_fp, tags_fp, relative_name, length

def prepare_files(
        input_dir: str, 
        output_dir: str,
        suffix: Optional[str]='.rdy',
        extract_tags: Optional[bool]=False,
    ):
    r"""
    Preprocess small files to prepare for translation.

    Returns:
        metadata: {created_fp: (relative_name, length, tags_fp)}
    """
    metadata = {}

    inputs = []
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            fp = os.path.join(root, f)
            inputs.append((fp, input_dir, output_dir, suffix, extract_tags))
    total = len(inputs)

    pbar = tqdm(total=total, desc="Preparing files")
    def callback(result):
        created_fp, tags_fp, relative_name, length = result
        metadata[created_fp] = (relative_name, length, tags_fp)
        pbar.update()

    p = multiprocessing.Pool(processes=CONFIG.CPU_COUNT)
    for i in range(pbar.total):
        p.apply_async(
            prepare_file, 
            args=inputs[i],
            callback=callback
        )
    p.close()
    p.join()

    return metadata

def wrap_files(
        metadata: dict,
        ordered_files: list,
        input_fp: str, 
        output_fp: str, 
        text_processor: TextProcessor, 
    ):
    r"""
    Split long lines in the input_fp into multiple lines in the new output_fp.
    Also finish any additional preprocessing that has to be done after this
    type of wrapping, e.g. prepending language tags.

    Returns:
        output_fp, updated_metadata
    """
    updated_metadata = {}
    with open(input_fp, 'r', encoding='utf-8') as infile, \
         open(output_fp, 'w', encoding='utf-8') as outfile:
        for fp in tqdm(ordered_files, desc="Wrapping long lines"):
            relative_name, length, tags_fp = metadata[fp]
            true_ids = []
            tagged = {}
            empties = set()
            j = 0
            for i in range(length):
                line = infile.readline()
                line = line.strip()
                if not line:
                    empties.add(j)
                if text_processor:
                    text, n = TextProcessor.wrap_text(
                        line, 
                        CONFIG.MAX_SENTENCE_LENGTH, 
                        after_wrap=text_processor.preprocess_after_wrap
                    )
                else:
                    text, n = TextProcessor.wrap_text(
                        line, 
                        CONFIG.MAX_SENTENCE_LENGTH
                    )
                for i in range(n):
                    true_ids.append(j)
                j += 1
                text = text.strip()
                outfile.write(text + os.linesep)
            updated_metadata[fp] = [relative_name, length, true_ids, empties, tags_fp]
    return output_fp, updated_metadata
        
def parse_stream_to_files(
        stream: IO,
        ordered_files: list, 
        metadata: dict, 
        output_dir: str,
        n_best: Optional[int]=1,
        n_best_words: Optional[bool]=False,
        suffix='.parsed'
    ):
    """
    Parse marian output, and write each line as we go to the output_dir,
    using the same relative name (i.e. directory structure) as described
    in the metadata. 

    Returns:
        parsed_files: ordered list of parsed files 
        parsed_metadata: {created_fp: (relative_name, true_ids, empties)}
    """
    #Must read in order and write in order so I'm not parallel processing this
    parsed_files = []
    parsed_metadata = {}
    for fp in tqdm(ordered_files, desc="Parsing"):
        relative_name, original_length, true_ids, empties, tags_fp  = metadata[fp]
        tgt_fp = os.path.join(output_dir, relative_name) + suffix
        os.makedirs(os.path.dirname(tgt_fp), exist_ok=True)

        if n_best_words: #alham's decoder
            parsed = parse_nbest_words(stream, len(true_ids), n_best)
        else: #normal marian
            parsed = parse(stream, len(true_ids), n_best)

        with open(tgt_fp, 'w', encoding='utf-8') as new_fh:
            for item in parsed:
                text = json.dumps(item, ensure_ascii=False, sort_keys=True)
                new_fh.write(text + os.linesep)

        parsed_files.append(tgt_fp)
        parsed_metadata[tgt_fp] = (relative_name, original_length, true_ids, empties, tags_fp)
    return (parsed_files, parsed_metadata)
    
def unwrap_and_postprocess_file(
        input_fp: str, 
        output_fp: str, 
        true_ids: list, 
        empties: set,
        tags_fp: str,
        text_processor: TextProcessor,
        n_best: Optional[int]=1,
        fmt: Optional[str]='json',
    ):
    """
    Read the json-lines in the input_fp, and combine those lines that were
    split into longer lines during preprocessing using the true_ids list.
    """ 
    os.makedirs(os.path.dirname(output_fp), exist_ok=True)
    with open(input_fp, 'r', encoding='utf-8') as infile:
        parsed = [json.loads(line.strip()) for line in infile] 

    tagged = {}
    if tags_fp:
        with open(tags_fp, 'r', encoding='utf-8') as infile:
            for j, line in enumerate(infile):
                tags = json.loads(line)
                if tags:
                    tagged[j] = tags

    final = unwrap_lines(
        parsed=parsed, 
        true_ids=true_ids,
        text_processor=text_processor,
        empties=empties,
        tagged=tagged,
        n_best=n_best,
    )
    logger.debug(
        f"{input_fp} {output_fp} " \
        f"original_length={len(true_ids)} "\
        f"parsed={len(parsed)} "\
        f"unwrapped={len(final)}"
    )
    with open(output_fp, 'w', encoding='utf-8') as new_fh:
        for item in final:
            text = fmt_item(item, fmt)
            new_fh.write(text + '\n')
    return output_fp

def postprocess_files(metadata, output_dir, text_processor, n_best, fmt, suffix=''):
    """
    Postprocess small files in parallel. Apply the text_processor and 
    unwrap lines, and write them to output_dir with the same relative name
    (i.e. directory structure) as in the metadata.
    """
    inputs = []
    for input_fp in metadata:
        relative_name, original_length, true_ids, empties, tags_fp = metadata[input_fp]
        output_fp = os.path.join(output_dir, relative_name) + suffix
        inputs.append(
            [input_fp, output_fp, true_ids, empties, tags_fp, text_processor, n_best, fmt]
        )

    total = len(inputs)
    pbar = tqdm(total=total, desc="Postprocessing")
    def postprocess_callback(result):
        pbar.update()

    p = multiprocessing.Pool(processes=CONFIG.CPU_COUNT)
    for i in range(pbar.total):
        p.apply_async(
            unwrap_and_postprocess_file, 
            args=inputs[i],
            callback=postprocess_callback
        )
    p.close()
    p.join()


def translate(
        subcommand: list,
        input_dir: str, 
        output_dir: str,
        text_processor: TextProcessor,
        n_best: Optional[int]=1,
        n_best_words: Optional[bool]=False,
        fmt: Optional[str]='json',
        extract_tags: Optional[bool]=True,
        purge: Optional[bool]=True,
    ):
    assert fmt in CONFIG.FMTS, f'Expected one of {CONFIG.FMTS} for fmt. Received fmt={fmt}'

    tmpdir = os.path.join(output_dir, 'tmp')
    os.makedirs(tmpdir, exist_ok=True)
    stderr_log = os.path.join(tmpdir, 'marian.log')
    big_fp = os.path.join(tmpdir, 'tmp.src')
    tgt_fp = os.path.join(tmpdir, 'tmp.tgt')

    #clean > sort + cat > preproc > wrap > translate > postproc + unwrap
    metadata = prepare_files(input_dir, tmpdir, '.rdy', extract_tags) 
    ordered_files = cat_files(tmpdir, big_fp, '.rdy') 
    preproc_fp = text_processor.preprocess_before_wrap_file(big_fp, big_fp + '.preproc')
    wrap_fp, metadata = wrap_files( 
        metadata=metadata, 
        ordered_files=ordered_files, 
        input_fp=preproc_fp, 
        output_fp=os.path.join(tmpdir, 'tmp.input'), 
        text_processor=text_processor,
    )
    if CONFIG.DEBUG:
        process_file(subcommand, wrap_fp, tgt_fp)
    else:
        process_file(subcommand, wrap_fp, tgt_fp, stderr_log) #translate
    with open(tgt_fp, 'r', encoding='utf-8') as infile:
        parsed_ordered_files, parsed_metadata = parse_stream_to_files(
            infile, ordered_files, metadata, tmpdir, n_best, n_best_words
        )
    postprocess_files(parsed_metadata, output_dir, text_processor, n_best, fmt=fmt)

    if purge:
        logger.info("Cleaning up")
        shutil.rmtree(tmpdir)

    return True

