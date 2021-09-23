#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
r"""
Run the translation pipeline in a server with settings set up from
existing environment variables. 
"""
import argparse
import asyncio
import io
import json
import logging
import os
import sys
from typing import *

import websockets 

from edinmt import CONFIG
from edinmt.get_settings import get_decoder_settings
from edinmt.parse_marian import (
    parse, 
    parse_nbest_words, 
    unwrap_lines,
    fmt_item,
)
from edinmt import retagger
from edinmt.text_processors.text_processors import TextProcessor

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.launch.launch_pipeline_server')
logger.setLevel(CONFIG.LOG_LEVEL)

marian_url = CONFIG.MARIAN + '/translate'
root_dir = CONFIG.ROOT_DIR
port = CONFIG.PIPELINE_PORT
host = CONFIG.PIPELINE_HOST
use_query = CONFIG.QUERY
max_length = CONFIG.MAX_SENTENCE_LENGTH

#TODO I think we should convert to FastAPI for this, so we get all the
#error handling and input/output parsing for free
async def server_func(ws, path):
    r"""
    Receive json formatted data on the websocket `ws` connection:
    {"src_lang": "xx", "tgt_lang": "yy", "text": "sent0\nsent1"}

    Preprocess text using the text pre-/post-processor,
    translate it using the marian-server running at `marian_url`,
    postprocess the result using the text pre-/post-processor, 
    and return outputs one line at a time to the websocket.
    """
    async for input_batch in ws:

        data = json.loads(input_batch)

        #collect the metadata we need
        text = data['text']
        src_lang = data['src_lang']
        tgt_lang = data['tgt_lang']

        decoder_settings = get_decoder_settings(src_lang, tgt_lang)
        tp = decoder_settings.text_processor
        warning = None

        lines = text.strip().split('\n')

        #if there are queries, make sure the user gave one for every sentence
        query = None
        if use_query and 'query' in data:
            query = data['query'].split('\n')
            if len(query) != len(lines):
                error = f"ERROR: Number of newline separated sentences "\
                        f"({len(lines)}) and queries ({len(query)}) differ. "\
                        f"(Empty queries are allowed but need newlines "\
                        f"around them to equal the number of sentences.)"
                logger.debug(f"{error}")
                response = {'error': error} 
                response = json.dumps(response, ensure_ascii=False, sort_keys=True)
                await ws.send(response)
                continue
        elif 'query' in data:
            warning = f"Warning: query guided translation not supported "\
                      f"by this model ({CONFIG.SYSTEM}). Query ignored." 
            logger.debug(f"{warning}")

        #split long lines into multiple pieces; track original line ids
        true_ids = []
        #find original empty lines to blank them out in case of hallucination
        empties = set()
        #extract urls, emails, xml tags to reisert in the output later 
        tagged = {}
        j = 0
        src = ""
        for i, line in enumerate(lines):
            if not line:
                empties.add(i)

            if decoder_settings.extract_tags:
                line, tags = retagger.extract_tags(line)
                if tags:
                    tagged[i] = tags

            #currently the query text processors accept tab-separated input
            if query:
                line = f"{line}\t{query[i]}"

            #wrap text and do remaining preprocessing (add multiling tags, etc)
            proc, length = TextProcessor.wrap_text(
                line, 
                max_length, 
                before_wrap=tp.preprocess_before_wrap,
                after_wrap=tp.preprocess_after_wrap
            )

            logger.debug(f"{proc}")
            if length > 1:
                logger.debug(f"LONG LINE SPLIT INTO {length} PIECES: {line}") 

            for k in range(length):
                true_ids.append(j)
            src += proc.strip() + '\n'
            j += 1

        #translate with marian
        logger.debug(f"SEND: {src}")
        #websockets pings the connection every once in a while to check if
        #it's still running but our marian server is silent for a long time
        #while it works, which causes the connection to get closed with 1006
        #so for this reason I set ping_timeout=None, but I'm not sure if this
        #is the best way to solve this; see also:
        #https://stackoverflow.com/questions/54101923/1006-connection-closed-abnormally-error-with-python-3-7-websockets
        #https://websockets.readthedocs.io/en/stable/api.html#websockets.protocol.WebSocketCommonProtocol
        async with websockets.connect(marian_url, ping_timeout=None, max_size=None) as marian_ws:
            await marian_ws.send(src) 
            response = await marian_ws.recv()
        logger.debug(f"RECV: {response}")

        #parse the marian outputs
        mtout = io.BytesIO(response.encode('utf-8'))
        if decoder_settings.n_best_words:
            parsed = parse_nbest_words(
                mtout, n_items=None, n_best=decoder_settings.n_best)
        else:
            parsed = parse(
                mtout, n_items=None, n_best=decoder_settings.n_best)
        
        logger.debug(f"PARSED {parsed}")

        #re-join the previously split long lines 
        final = unwrap_lines(
            parsed,
            true_ids,
            text_processor=tp,
            empties=empties,
            tagged=tagged,
            n_best=decoder_settings.n_best, 
            expand=True
        )
        for item in final:
            if warning:
                item['warning'] = warning
            text = fmt_item(item, decoder_settings.fmt)

            #return output to the user
            await ws.send(text)


if __name__ == "__main__":
    logger.info(f"Launching pipeline server on ws://{host}:{port}")
    start_server = websockets.serve(server_func, host, port)
    asyncio.get_event_loop().run_until_complete(start_server)

    asyncio.get_event_loop().run_forever()
