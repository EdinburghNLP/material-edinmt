import argparse
import json
import logging
import os
import shutil
import subprocess
from typing import *

import yaml
from pydantic import BaseModel, validator

from edinmt import CONFIG
from edinmt.scorers import SCORERS, Scorer
from edinmt import translate_file
from edinmt.get_settings import get_decoder_settings

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.score_test_sets')
logger.setLevel(CONFIG.LOG_LEVEL)

class DatasetConfig(BaseModel):
    src_lang: str
    tgt_lang: str
    src: list
    ref: list
    scorers: Optional[dict]={}
    text_processor: Optional[dict]={}
    preprocess: Optional[bool]=True

    @validator('src', 'ref')
    def valid_file(cls, data):
        for v in data:
            if not os.path.exists(v):
                raise FileNotFoundError(f"File not found: {v}")
        return data

class ConfigArgs(BaseModel):
    data: Dict[str, DatasetConfig]

def main(
        config,
        outdir,
        use_mode=None,
        systems_dir=None,
        system=None,
        marian_args=None
    ):
    r"""
    Run the translation pipeline (which invokes marian-decoder) to
    translate multiple test sets described in the config file using
    the appropriate models from the system. 

    Args:
        config: config file with test sets
        outdir: output directory to put intermediate files into
        use_mode: "fast" for single model, "accurate" for ensemble
        systems_dir: local of the systems
        system: the system to use for scoring (folder inside the systems dir)
        marian_args: extra marian args passed directly to marian-decoder

    Example config:
        { data: { 
                my_test_set1: {
                    src_lang: xx,
                    tgt_lang: yy,
                    src: [source_file, multisource_extra_input1, ...],
                    ref: [ref_1, ref_2, ...],
                    scorers: { 
                        SacrebleuScorer: {arg1: xxx, ...}
                    },
                    text_processor: {arg1: yyy, ...},
                    preprocess: True
                },
                my_test_set2: {...}
            }
        }
    
    NOTE: This will search for the marian-decoder and other settings. To run
    outside of the Docker system, set the environment variables in 
    edinmt.configs.config.Config correctly, in particular: 
     - MARIAN_BUILD_DIR

    TODO: we currently only supprt a ref list of length 1
    """
    os.makedirs(outdir, exist_ok=True)

    user_settings = {
        'MODE': use_mode,
        #We don't support scoring n-best translations with this score pipeline
        'NBEST_WORDS': False,
        'NBEST': False,
        #we use text because we create the plaintext file for comparison 
        'FMT': 'text'
    }
    if systems_dir:
        user_settings['SYSTEMS_DIR'] = systems_dir
    if system:
        user_settings['SYSTEM'] = system

    results = {}
    for k in config.data:
        settings = user_settings.copy() #make a new copy each iter to refresh
        settings.update(config.data[k].text_processor)
        src_lang, tgt_lang = config.data[k].src_lang, config.data[k].tgt_lang
        this_outdir = os.path.join(outdir, k)
        os.makedirs(this_outdir, exist_ok=True)

        settings['SRC'] = src_lang
        settings['TGT'] = tgt_lang
        decoder_settings = get_decoder_settings(
            src_lang, 
            tgt_lang, 
            user_settings=settings, 
            extra_args=marian_args
        )
        src_data, ref_data = config.data[k].src, config.data[k].ref

        final_fp = translate_file.translate(
            decoder_settings.cmd,
            src_data, 
            this_outdir, 
            text_processor=decoder_settings.text_processor,
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt,
            extract_tags=decoder_settings.extract_tags,
            preprocess=config.data[k].preprocess
        )

        results[k] = {}
        for scorer_name in config.data[k].scorers:
            scorer = SCORERS[scorer_name](**config.data[k].scorers[scorer_name])
            #we only support 1 reference in this score pipeline
            score = scorer.score_file(final_fp, ref_data[0]) 
            logger.debug(f"{k} {scorer_name} {score} (SRC {final_fp} -VS- REF {ref_data[0]})")
            results[k][scorer_name] = score 

    results_fp = os.path.join(outdir, 'results.json')
    with open(results_fp, 'w', encoding='utf-8') as results_fh:
        json.dump(results, results_fh)

    logger.info(f"{results}") 
    return results_fp


def parse_args():
    import textwrap

    class Formatter(
            argparse.ArgumentDefaultsHelpFormatter, 
            argparse.RawDescriptionHelpFormatter
        ): 
        pass

    epilog = textwrap.dedent(f"""
        Example config.yml:
        -------------------
          data:
            my_test_set:
              src_lang: xx
              tgt_lang: yy
              src: 
                - source_file 
                - multisource_extra_input1
              ref: 
                - reference_file
              scorers: 
                SacrebleuScorer:
              text_processor: (any additional args the text processor needs)
              preprocess: (default true; false for already preprocessed data)

        Available scorers: {[k for k in SCORERS.keys() if k != 'Scorer']}
    """)

    parser = argparse.ArgumentParser(
        formatter_class=Formatter,
        description="Evaluate a model on test sets using the scorer.",
        epilog=epilog
    )
    parser.add_argument('config', help='path to config.yml file')
    parser.add_argument('outdir', 
        help="output directory where to save the evaluation results")
    parser.add_argument('--mode', default=CONFIG.MODE, choices=["fast", "accurate"],
        help='determines which marian config to use')
    parser.add_argument('--systems_dir', default=CONFIG.SYSTEMS_DIR, 
        help='directory where systems are located')
    parser.add_argument('--system', default=CONFIG.SYSTEM, 
        help='name (subdir) of the system to use')
    args, rest = parser.parse_known_args()
    args.rest = rest

    return args

if __name__ == '__main__':
    args = parse_args()
    with open(args.config, 'r', encoding='utf-8') as infile:
        config = yaml.safe_load(infile)
    logger.info(f'Score test sets: {config}')
    pconfig = ConfigArgs.parse_obj(config)
    main(
        pconfig,
        outdir=args.outdir,
        use_mode=args.mode,
        systems_dir=args.systems_dir,
        system=args.system,
        marian_args=args.rest
    )
