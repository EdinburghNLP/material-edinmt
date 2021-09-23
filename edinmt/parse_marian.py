#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-
import json
import logging
import os
from typing import *
from typing import IO #the * above won't load this

from edinmt import CONFIG
from edinmt import retagger
from edinmt.text_processors import TextProcessor

logger = logging.getLogger('edinmt.parse_marian')
logger.setLevel(CONFIG.LOG_LEVEL)
#only translation output should go on stdout so we remove StreamHandlers
handlers = logger.handlers.copy()
logger.handlers = [h for h in handlers if not isinstance(h, logging.StreamHandler)]

def parse(
        process_stdout: IO, 
        n_items: Optional[int]=None, 
        n_best: Optional[int]=1,
        mtout: Optional[IO]=None,
    ):
    r"""
    Convert Marian format into list of dicts, one dict per translation.
    If n-best sentences are used, each n-best is still its own dict.
    
    Args:
        process_stdout: an iterator over lines of string translations where 
            each translation is a triple pipes delimited 4-tuple such as: 
            "id ||| translation ||| F0 ||| score\n"
        n_items: the number of items you want to read from process_stdout
            (default=None reads all items from the process_stdout)
        n_best: each final output item should actually consist of n-best
            translations (default=1 means each final output is 1 translation)
        mtout: stream to write raw marian output to directly (optional)

    Returns:
        outputs: ordered list of dictionaries, one dict per translation item
    """
    batch = []
    count = 0
    n_best_count = 0
    item = {}

    nbest_translations = []
    for line in process_stdout:
        if mtout:
            mtout.write(line)

        try:
            decoded = line.decode('utf-8')
        except AttributeError:
            pass #it's already a string not bytes; no need to decode
        else:
            line = decoded

        n_best_count += 1 
        if ' ||| ' in line: #n-best marian
            sent_id, translation, f0, score = line.split(' ||| ')
            nbest_translations.append(translation)
            if n_best_count == n_best:
                item = {
                    'id': count,
                    'translation': nbest_translations
                }
                batch.append(item) #FINISH ITEM
                nbest_translations = []
                count += 1
                n_best_count = 0
        else: #normal marian
            item = {
                'id': count,
                "translation": [line], 
            }
            batch.append(item) #FINISH ITEM
            item = {}
            count += 1
        
        if count == n_items:
            break

    return batch
        

def parse_nbest_words(
        process_stdout: IO, 
        n_items: Optional[int]=None, 
        n_best: Optional[int]=1,
        mtout: Optional[IO]=None,
    ):
    r"""
    Convert Marian format into list of dicts, one dict per translation.
    The n-best tokens in each position (decoder from Alham), get added 
    to the translation dict as a list of "n_best_words" dicts.
    
    Args:
        process_stdout: an iterator over lines of string translations where 
            each translation is a triple pipes delimited 4-tuple such as 
            "id ||| translation ||| F0 ||| score\n"
            and new-line separated n-best tokens underneath, such as
            "tok1 ||| tok1 score tok2 score\n"
            and an empty line afterwards, delimiting the translation
        n_items: the number of items you want to read from process_stdout
            (default=None reads all items from the process_stdout)
        n_best: each final output item should actually consist of n-best
            translations (default=1 means each final output is 1 translation)
        mtout: stream to write raw marian output to directly (optional)

    Returns:
        outputs: ordered list of dictionaries, one dict per translation item

    NOTE: n-best words decoder output available using Alham's decoder:
    https://github.com/afaji/Marian/tree/alt-words
    """
    batch = []
    count = 0
    n_best_count = 0
    parsing = False

    transl = ""
    nbestw = []
    translation = []
    nbest_words = []
    for line in process_stdout:
        if mtout:
            mtout.write(line)

        try:
            decoded = line.decode('utf-8')
        except AttributeError:
            pass #it's already a string not bytes; no need to decode
        else:
            line = decoded
        line = line.strip()

        if line:
            parsing = True
            try:
                sent_id, sent, f0, score = line.split(' ||| ')
            except ValueError:
                token, rest = line.split('|||')
                nbests = rest.split()
                d = {}
                for r in range(0, len(nbests), 2):
                    d[nbests[r]] = nbests[r+1]
                nbestw.append(d)
                if token != '</s> ':
                    transl += token
            else:
                continue

        elif not line and parsing:
            translation.append(transl.strip())
            nbest_words.append(nbestw)
            transl = ""
            nbestw = []
            n_best_count += 1 
            parsing = False
            if n_best_count == n_best:
                item = {
                    'id': count,
                    'translation': translation,
                    'nbest_words': nbest_words
                }
                batch.append(item) #FINISH ITEM
                translation = []
                nbest_words = []
                count += 1
                n_best_count = 0

        elif not line and not parsing:
            continue #skip 2nd empty line
        
        if count == n_items:
            break
    
    if parsing: #last one can be missed if there's no empty line at eof
        translation.append(transl.strip())
        nbest_words.append(nbestw)
        item = {
            'id': count,
            'translation': translation,
            'nbest_words': nbest_words
        }
        batch.append(item) #FINISH ITEM

    return batch

def unwrap_lines(
        parsed: list,
        true_ids: list,
        text_processor: Optional[TextProcessor]=None,
        empties: Optional[set]=None,
        tagged: Optional[dict]=None,
        n_best: Optional[int]=1, 
        expand: Optional[bool]=True
    ):
    """
    Join together parsed items that were created from a single original item
    that got split into multiple lines in preprocessing. Postprocess the
    translations. Items that used to be empty can be blanked out using 
    a set of empty ids (original line numbers from the original text).
    Items that had text snippets extracted and replaced with [TAG] tokens can
    have text reinserted in place of the [TAG] token using the tagged dict.

    Warning! Entire parsed output will be held in memory. If this is
    a problem, please provide batches of parsed items instead.

    Args:
        parsed: a batch of items as output by parse or parse_nbest_words
        true_ids: true ids for each item in parsed 
        text_processor: TextProcessor to .postprocess() text with
        empties: original ids that should be blanked out 
        tagged: line numbers to tuples of ([TAG], text) 
        n_best: number of n-best sentences (>1 if marian's --n-best was used)
        expand: expand n-best items into their own item
    """
    final = []

    collated = {}
    true_ids_iter = iter(true_ids)
    last_true_id = 0
    
    #combine the split parsed item into one item with a list of split outputs
    #e.g. for a sentence with pieceN_topN we have a transformation of:
    #[p0_t1, p0_t2, p1_t1, p1_t1] -> [[p0_t1, p0_t2], [p1_t1, p1_t1]]
    for item in parsed:
        true_id = int(next(true_ids_iter))
        if true_id not in collated:
            collated[true_id] = {'id': true_id, 'translation': []}
            if 'nbest_words' in item:
                collated[true_id]['nbest_words'] = []

        collated[true_id]['translation'].append(item['translation'])
        if 'nbest_words' in item:
            collated[true_id]['nbest_words'].append(item['nbest_words'])
        last_true_id = true_id

    #now combine the n-best sentences into one item, and also debpe, etc.
    #e.g. for a sentence with pieceN_topN we have a transformation of:
    #[[p0_t1, p0_t2], [p1_t1, p1_t1]] -> [p0_t1_p1_t1, p0_t2_p1_t2]
    for idx in collated:
        item = collated[idx]
        if empties and item['id'] in empties: #blank out hallucinations
            item['translation'] = ['']*n_best
            if 'nbest_words' in item:
                item['nbest_words'] = [[]]*n_best
        else:
            transl = list(zip(*item['translation']))
            all_translations = []
            for tup in transl:
                translation = ' '.join([t.strip() for t in tup])
                if text_processor:
                    #debpe, detruecase, etc.
                    translation = text_processor.postprocess(translation).strip()
                    if tagged and item['id'] in tagged:
                        tags = tagged[item['id']]
                        #reinsert urls, emails, etc. that we had passed through
                        translation = retagger.reinsert_tags(translation, tags)
                all_translations.append(translation)
            item['translation'] = all_translations

            if 'nbest_words' in item:
                nbestw = list(zip(*item['nbest_words']))
                all_nbest_words = []
                for tup in nbestw:
                    nbest_words = []
                    for l in tup:
                        for i in l:
                            nbest_words.append(i)
                    all_nbest_words.append(nbest_words)
                item['nbest_words'] = all_nbest_words

        #now separate the n-best sentences into their own separate json-lines
        #so we have json-line per n-best instead of n-bests inside 1 json
        if expand: 
            for i in range(len(item['translation'])):
                tmp_item = {
                    'id': item['id'],
                    'translation': item['translation'][i]
                }
                if 'nbest_words' in item:
                    tmp_item['nbest_words'] = item['nbest_words'][i]
                final.append(tmp_item)
        else:
            final.append(item)

    return final 

def fmt_item(item, fmt):
    r"""Format the item to the correct output format (choices: CONFIG.FMTS)."""
    if fmt == 'json':
        text = json.dumps(item, ensure_ascii=False, sort_keys=True)
    elif fmt == 'marian':
        text = f"{item['id']} ||| {item['translation'].strip()}"
    elif fmt == 'text':
        text = f"{item['translation'].strip()}"
    return text
