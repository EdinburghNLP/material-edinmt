import json
import logging
import os
import shutil
import subprocess
import sys
from typing import *

from edinmt import CONFIG
from edinmt.parse_marian import (
    parse, 
    parse_nbest_words, 
    unwrap_lines,
    fmt_item
)
from edinmt.text_processors.text_processors import (
    TextProcessor
)
from edinmt import retagger

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.translate_file')
logger.setLevel(CONFIG.LOG_LEVEL)

def clean_file(input_fp: str, outfp: str) -> None:
    r"""
    We have to get rid of lonely \r in files, because otherwise, if we iterate
    over the file, and pass it to marian, we get fake newlines back, messing
    up the count of lines, the parsing, and the line reading.
    """
    cmd = f'sed -e "s/\r//g" {input_fp} > {outfp}'
    subprocess.check_output(cmd, shell=True)
    return outfp

def process_file(
        cmd: list,
        src_fp: str,
        tgt_fp: str,
        stderr_log: Optional[str]=None,
    ) -> int:
    r"""
    Invoke the cmd using the src_fp as input and the tgt_fp as output.
    (The main use case is to translate a source file into a target file
    using the marian command.)

    Args:
        cmd: e.g. ~/marian/build/marian-decoder -c cfg.yml --devices 0
        src_fp: source file to feed into cmd
        tgt_fp: target file to output from cmd
        stderr_log: filepath of log file (default outputs to sys.stderr)

    Returns:
        0 if success, otherwise cmd's returncode
    """
    cmd = ' '.join(cmd)
    cmd = f"{cmd} < {src_fp} > {tgt_fp}"
    logger.info(f'RUNNING: {cmd}')
    try:
        if stderr_log:
            logger.info(f'Watch {stderr_log} for updates.')
            with open(stderr_log, 'wb') as outfile:
                subprocess.check_output(cmd, stderr=outfile, shell=True) 
        else:
            subprocess.check_output(cmd, stderr=sys.stderr, shell=True) 
    except subprocess.CalledProcessError as e:
        return e.returncode 
    else:
        return 0

def wrap_and_preprocess_file(
        input_fp: str, 
        output_fp: str, 
        text_processor: TextProcessor,
        preprocess: Optional[bool]=True,
        extract_tags: Optional[bool]=False,
    ) -> tuple:
    """
    Preprocess the file and split long lines into multiple lines.
    Return the new filepath, and a mapping of the id of each line in the
    new file to the old original file lines, e.g. [0, 0, 1, 2, ...].
    """
    max_length = int(CONFIG.MAX_SENTENCE_LENGTH)

    #We have to get rid of lonely \r in files, because otherwise, if we
    #iterate over the file and pass it to marian, we get fake newlines, 
    #messing up the count of lines, the line reading, and the parsing.
    cleaned = output_fp + '.clean'
    if not os.path.exists(cleaned):
        logger.info(f"Cleaning (removing \\r) {input_fp}")
        cleaned = clean_file(input_fp, cleaned)
    else:
        logger.info(f"Using pre-cleaned {cleaned}")

    #Preprocess before wrapping lines using the preprocessor (e.g. bpe,
    #before adding language tags for multilingual preprocessors; the second
    #part will happen below, during line wrapping)
    fp = cleaned
    prep_fp = fp + text_processor.ext
    if text_processor and preprocess and not os.path.exists(prep_fp):
        logger.info(f"Preprocessing with {type(text_processor).__name__}: {fp} -> {prep_fp}")
        fp = text_processor.preprocess_before_wrap_file(cleaned, prep_fp)
    else:
        logger.info(f"Using preprocessed {prep_fp}")

    #We find blank lines in files because the model can hallucinate on
    #blank lines (especially for multilingual models), so we'll want to
    #manually blank them out later in the output.
    true_ids = []
    empties = set()
    tagged = {}
    with open(fp, 'r', encoding='utf-8') as infile, \
         open(output_fp, 'w', encoding='utf-8') as outfile:
        j = 0
        for k, line in enumerate(infile):
            line = line.strip()

            if not line:
                empties.add(j)

            if extract_tags:
                line, tags = retagger.extract_tags(line)
                if tags:
                    tagged[i] = tags

            if text_processor and preprocess:
                text, n = TextProcessor.wrap_text(
                    line, 
                    max_length, 
                    after_wrap=text_processor.preprocess_after_wrap
                )
            else:
                text, n = TextProcessor.wrap_text(line, max_length)

            if n > 1:
                logger.debug(f"LONG LINE {k} broken in {n} pieces")
            for i in range(n):
                true_ids.append(j)
            outfile.write(text + os.linesep)
            j += 1
    return (input_fp, output_fp, true_ids, empties, tagged)

def translate(
        marian_cmd: str, 
        srcs: list, 
        outdir: str, 
        text_processor: TextProcessor, 
        n_best: Optional[int]=1, 
        n_best_words: Optional[bool]=False,
        fmt: Optional[str]='json',
        extract_tags: Optional[bool]=False,
        preprocess: Optional[bool]=True,
    ) -> str:
    """
    Translate a source file.

    Args:
        marian_cmd: e.g. ~/marian/build/marian-decoder -c cfg.yml --devices 0
        srcs: source filepath and any additional (multisource) inputs
        outdir: directory to put the final translated outputs and tmp files
        text_processor: TextProcessor for bpe, tokenization, truecasing, etc.
        n_best: number of n_best the model outputs
        fmt: final output format, one of ['json', 'marian', 'text']

    Returns:
        output_fp: filepath of final translated output file
    """
    assert fmt in CONFIG.FMTS, f'expected fmt in {CONFIG.FMTS}; received {fmt}'

    #1. PREPROCESS
    relative_name = os.path.basename(srcs[0])
    ready = os.path.join(outdir, relative_name + '.rdy')
    result = wrap_and_preprocess_file(
        input_fp=srcs[0], 
        output_fp=ready, 
        text_processor=text_processor,
        preprocess=preprocess,
        extract_tags=extract_tags,
    )
    input_fp, output_fp, true_ids, empties, tagged = result

    inputs = [ready]
    #adjust the lines in multisource inputs to equal lines in main source file
    for fp in srcs[1:]:
        wrapped_fp = os.path.join(outdir, os.path.basename(fp) + '.wrapped')
        with open(fp, 'r', encoding='utf-8') as infile, \
             open(wrapped_fp, 'w', encoding='utf-8') as outfile:
            last_i = 0
            line = infile.readline().strip()
            if text_processor and preprocess:
                line = text_processor.preprocess_before_wrap(line).strip()
            for c, i in enumerate(true_ids):
                if i > last_i:
                    line = infile.readline().strip()
                    if text_processor and preprocess:
                        line = text_processor.preprocess_after_wrap(line).strip()
                    last_i = i
                outfile.write(line + '\n')
        inputs.append(wrapped_fp)

    #2. TRANSLATE 
    mtout_fp = ready + '.mtout.raw'
    if not os.path.exists(mtout_fp):
        logger.info(f"Translating {inputs} -> {mtout_fp}")
        translated = process_file(
            marian_cmd,
            ' '.join(inputs),
            mtout_fp
        )
    else:
        logger.info(f"Using pre-translated {mtout_fp}")

    #3. PARSE AND WRITE OUT TRANSLATIONS
    final_fp = ready + '.mtout.txt'
    if os.path.exists(final_fp):
        logger.info(f"Using pre-parsed output fp {final_fp}")
        return final_fp

    logger.debug(f"Parsing output {mtout_fp} -> {final_fp}")
    with open(mtout_fp, 'r', encoding='utf-8') as infile, \
         open(final_fp, 'w', encoding='utf-8') as outfile:
        if n_best_words: #alham's decoder
            parsed = parse_nbest_words(infile, len(true_ids), n_best)
        else: #normal marian
            parsed = parse(infile, len(true_ids), n_best)

        #glue long lines that were split over items
        final = unwrap_lines(
            parsed=parsed, 
            true_ids=true_ids,
            text_processor=text_processor,
            empties=empties,
            tagged=tagged,
            n_best=n_best,
        )

        logger.debug(f"{final_fp} original={len(true_ids)} parsed={len(parsed)} unwrapped={len(final)}")

        for item in final:
            text = fmt_item(item, fmt)
            outfile.write(text + '\n')
    return final_fp
