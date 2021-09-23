#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
import argparse
import inspect
import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from subprocess import PIPE
from typing import *
from typing import IO #the * above won't load this

import websocket

from edinmt import CONFIG
from edinmt.parse_marian import (
    parse, 
    parse_nbest_words, 
    unwrap_lines, 
    fmt_item
)
from edinmt.text_processors import TEXT_PROCESSORS
from edinmt.text_processors.text_processors import TextProcessor
from edinmt import retagger

logger = logging.getLogger(__name__)
logger.setLevel(CONFIG.LOG_LEVEL)
#only translation output should go on stdout so we remove StreamHandlers
handlers = logger.handlers.copy()
logger.handlers = [h for h in handlers if not isinstance(h, logging.StreamHandler)]

def read( 
        input_fh: IO, 
        process_stdin: IO, 
        q: queue.Queue, 
        text_processor: Optional[TextProcessor]=None,
        batch_size: Optional[int]=1, 
        extract_tags: Optional[bool]=False,
    ):
    r"""Read text from input_fh, send to process_stdin."""
    count = 0
    batch = ""
    empties = set()
    true_ids = []
    tagged = {}
    for i, text in enumerate(input_fh): 
        text = text.decode('utf-8') if sys.version_info < (3, 0) else text
        text = text.strip()

        if not text:
            empties.add(count)

        if extract_tags:
            text, tags = retagger.extract_tags(text)
            if tags:
                tagged[i] = tags

        #split long lines into pieces; track original line ids in true_ids
        src = ""
        for line in text.split('\n'):
            if text_processor:
                line, n = TextProcessor.wrap_text(
                    text, max_length=CONFIG.MAX_SENTENCE_LENGTH,
                    before_wrap=text_processor.preprocess_before_wrap,
                    after_wrap=text_processor.preprocess_after_wrap,
                )
            else:
                line, n = TextProcessor.wrap_text(
                    text, 
                    max_length=CONFIG.MAX_SENTENCE_LENGTH
                )

            if n > 1:
                logger.debug(f"LONG LINE {count} SPLIT INTO {n} PIECES: {line}") 
            for k in range(n):
                true_ids.append(count)
            src += line.strip() #normalize line endings over text processors
        
        batch += src + '\n'
        count += 1

        if count == batch_size:
            process_stdin.write(batch.encode('utf-8'))
            q.put((count, empties, true_ids, tagged))
            count = 0
            batch = ""
            empties = set()
            tagged = {}
            true_ids = []

    if batch != "": #don't forget the last batch of remainder sents 
        process_stdin.write(batch.encode('utf-8'))
        q.put((count, empties, true_ids, tagged))

    q.put(None) #poison
    process_stdin.close()

def write( 
        output_fh: IO, 
        process_stdout: IO, 
        q: queue.Queue, 
        text_processor: Optional[TextProcessor]=None,
        batch_size: Optional[int]=1,
        n_best: Optional[int]=1,
        n_best_words: Optional[bool]=False,
        fmt: Optional[str]='json',
    ):
    r"""
    Receive text from process_stdout, write to output_fh in chunks,
    according to the count stored in the q.
    """
    sentence_id = 0
    while True:
        result = q.get()
        if result is None:
            break

        _, empties, true_ids, tagged = result
        n_items = len(true_ids)
        
        if n_best_words: #alham's decoder
            parsed = parse_nbest_words(process_stdout, n_items, n_best)
        else: #normal marian
            parsed = parse(process_stdout, n_items, n_best)

        #re-join the previously split long lines 
        final = unwrap_lines(
            parsed,
            true_ids,
            text_processor=text_processor,
            empties=empties,
            tagged=tagged,
            n_best=n_best, 
        )

        i = 0
        for item in final:
            #always increment sent id but also count it based on n_best
            if i == n_best: 
                sentence_id += 1
                i = 0
            item["id"] = sentence_id

            text = fmt_item(item, fmt)

            output_fh.write(text + '\n')
            i += 1
        sentence_id += n_items
        
        q.task_done()


def translate( 
        subcommand: list, 
        input_fh: Optional[IO]=sys.stdin, 
        output_fh: Optional[IO]=sys.stdout,
        text_processor: Optional[TextProcessor]=None,
        batch_size: Optional[int]=1,
        n_best: Optional[int]=1,
        n_best_words: Optional[bool]=False,
        fmt: Optional[str]='json',
        extract_tags: Optional[bool]=False,
    ):
    logger.debug(f"RUNNING: {' '.join(subcommand)}")

    process = subprocess.Popen(
        ' '.join(subcommand), 
        stdin=PIPE, stdout=PIPE, stderr=sys.stderr, shell=True
    )

    q = queue.Queue()
    reader = threading.Thread(
        target=read, 
        args=(input_fh, process.stdin, q, text_processor, 
              batch_size, extract_tags)
    )
    writer = threading.Thread(
        target=write, 
        args=(output_fh, process.stdout, q, text_processor, 
              batch_size, n_best, n_best_words, fmt)
    )
    reader.start()
    writer.start()
    reader.join()
    writer.join()

    return process.wait()
