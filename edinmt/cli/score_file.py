import argparse
import json
import logging
import os
import shutil
import subprocess
from typing import *

from edinmt import CONFIG
from edinmt.get_settings import get_decoder_settings
from edinmt.translate_input import translate

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.score_file')
logger.setLevel(CONFIG.LOG_LEVEL)

def sacrebleu_score(prediction, reference):
    if isinstance(reference, list):
        reference = ' '.join(reference)
    cmd = f'cat {prediction} | sacrebleu {reference}'
    logger.debug('RUNNING: ' + cmd)
    result = subprocess.check_output(cmd, shell=True)
    result = result.decode()
    logger.debug(f"SACREBLEU RESULT: {result}")
    bleu = result.split(" = ")[1].split(" ")[0]
    return bleu 


def main(
        src_lang,
        tgt_lang, 
        src_fp,
        ref_fp,
        outdir=None,
        system_name=None, 
        use_mode=None, 
        marian_args=None
    ):
    r"""
    Run the translation pipeline (which invokes marian-decoder) to
    translate from stdin to stdout.

    Args:
        src_lang: source language (required for text pre/post text_processors)
        tgt_lang: source language (required for text pre/post text_processors)
        src_fp: source language input file to be translated
        ref_fp: reference target language file to evaluate against
        outdir: output directory to put intermediate files into
        system_name: name of the system directory in the SYSTEMS_DIR
        use_mode: "fast" for single model, "accurate" for ensemble
        marian_args: extra marian args passed directly to marian-decoder

    Side-effects:
        writes translations to stdout

    #NOTE: This will search for the marian-decoder and other settings. To run
    #outside of the Docker system, set the environment variables in 
    #edinmt.configs.config.Config correctly, in particular: 
    # - MARIAN_BUILD_DIR
    # - SYSTEMS_DIR 
    """
    if outdir is None:
        outdir = os.path.dirname(src_fp)
        if not outdir:
            outdir = '.'
    os.makedirs(outdir, exist_ok=True)

    user_settings = {'SRC': src_lang, 'TGT': tgt_lang} 
    if system_name is not None:
        user_settings['SYSTEM'] = system_name
    if use_mode is not None:
        user_settings['MODE'] = use_mode

    #We don't score n-best translations with this scoring pipeline
    user_settings['NBEST'] = False 
    user_settings['NBEST_WORDS'] = False
    #we use plaintext because we compare this directly to the ref
    user_settings['FMT'] = 'json'

    decoder_settings = get_decoder_settings(
        src_lang, tgt_lang, user_settings=user_settings, extra_args=marian_args
    )

    mtout_json_fp = os.path.join(outdir, os.path.basename(src_fp) + '.mtout.json')
    with open(src_fp, 'r', encoding='utf-8') as src_fh, \
         open(mtout_json_fp, 'w', encoding='utf-8') as mtout_fh:
        logger.debug(f"RUNNING: {' '.join(decoder_settings.cmd)}")
        translate(
            subcommand=decoder_settings.cmd,
            input_fh=src_fh,
            output_fh=mtout_fh,
            text_processor=decoder_settings.text_processor, 
            batch_size=decoder_settings.batch_size, 
            fmt=decoder_settings.fmt,
            extract_tags=decoder_settings.extract_tags,
        )

    mtout_text_fp = os.path.join(outdir, os.path.basename(src_fp) + '.mtout.txt')
    with open(mtout_json_fp, 'r', encoding='utf-8') as infile, \
         open(mtout_text_fp, 'w', encoding='utf-8') as outfile:
        for line in infile:
            data = json.loads(line)
            outfile.write(data['translation'] + '\n')
    
    score = sacrebleu_score(mtout_text_fp, ref_fp)
    logger.info(f"SacreBLEU SCORE {score} (SRC {mtout_text_fp} -VS- REF {ref_fp})")
    return score
    

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, 
        description="Evaluate a model on a test set using the sacrebleu scorer.",
    )
    parser.add_argument('src_lang', help='source language')
    parser.add_argument('tgt_lang', help='target language')
    parser.add_argument('src_fp', help='source language file to be translated')
    parser.add_argument('ref_fp', help='target language reference file to score against')
    parser.add_argument('--outdir', default=None,
        help="output directory where to save the evaluation results, default=src_fp's directory")
    parser.add_argument('--system', default=CONFIG.SYSTEM, 
        help='determines which included system to use')
    parser.add_argument('--mode', default=CONFIG.MODE, choices=["fast", "accurate"],
        help='determines which marian config to use')
    args, rest = parser.parse_known_args()
    args.rest = rest

    return args

if __name__ == '__main__':
    args = parse_args()
    main(
        src_lang=args.src_lang, 
        tgt_lang=args.tgt_lang, 
        src_fp=args.src_fp,
        ref_fp=args.ref_fp,
        outdir=args.outdir,
        use_mode=args.mode,
        marian_args=args.rest
    )