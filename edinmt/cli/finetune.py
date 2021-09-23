import argparse
import collections.abc
import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap
from typing import *

import yaml
from pydantic import BaseModel, validator

from edinmt import CONFIG
from edinmt.configs.config import all_members
from edinmt.text_processors import TEXT_PROCESSORS
from edinmt.text_processors.text_processors import TextProcessor
from edinmt.get_settings import get_decoder_settings
from edinmt.utils import get_file_length, fix_broken_chars

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.cli.finetune')
logger.setLevel(CONFIG.LOG_LEVEL)

class Formatter(
        argparse.ArgumentDefaultsHelpFormatter, 
        argparse.RawDescriptionHelpFormatter
    ): 
    r"""Format help text in the arg parser in a prettier way."""
    pass

class FinetuneError(BaseException):
    """Raise for errors finetuning the model."""

def clean_pair(this_outdir, src, tgt, set_name=''):
    r"""
    Fix broken chars that cause line numbering issues (e.g. \r) 
    in a parallel data set and check that lengths are identical.
    """
    name = set_name + '.' if set_name else ''
    cleaned_src = os.path.join(this_outdir, f'{name}src.clean')
    cleaned_tgt = os.path.join(this_outdir, f'{name}tgt.clean')
    if not os.path.exists(cleaned_src):
        cleaned_src = fix_broken_chars(src, cleaned_src)
        cleaned_tgt = fix_broken_chars(tgt, cleaned_tgt)
    src_length = get_file_length(cleaned_src)
    tgt_length = get_file_length(cleaned_tgt)
    if src_length != tgt_length:
        msg = f"{set_name} file lengths don't match: "\
            f"{cleaned_src} ({src_length}) and " \
            f"{cleaned_tgt} ({tgt_length})."
        logger.error(msg)
        raise FinetuneError(msg)
    return cleaned_src, cleaned_tgt, src_length

def main(
        src_lang, 
        tgt_lang, 
        output_dir,
        train_sets=list,
        valid_sets=list,
        system_name=None, 
        marian_args=None,
        force=False,
        dry_run=False
    ):
    r"""
    Run the translation pipeline (which invokes marian-decoder) to
    translate from stdin to stdout.

    Args:
        src_lang: source language (required for text pre/post text processors)
        tgt_lang: source language (required for text pre/post text processors)
        output_dir: directory where to place the new system
        train_sets: 2-length list of source and target training data
        valid_sets: 2-length list of source and target validation data
        system_name: name of the system directory in the SYSTEMS_DIR
        marian_args: extra marian args passed directly to marian-decoder
        force: overwrite pre-existing fine-tuned model; WARNING DESTRUCTIVE!

    Side-effects:
        creates the output_dir with a new system inside of it 

    #NOTE: This will search for the marian-decoder and other settings. To run
    #outside of the Docker system, set at least these environment variables:
    # - MARIAN_BUILD_DIR
    # - SYSTEMS_DIR 
    """
    #Gather the settings we used from the original model to
    #get the correct system name for the new traindir we want to create
    user_settings = {'SRC': src_lang, 'TGT': tgt_lang} 
    if system_name is not None:
        user_settings['SYSTEM'] = system_name
    decoder_settings = get_decoder_settings(
        src_lang, tgt_lang, user_settings=user_settings, extra_args=marian_args
    )
    output_system_dir = os.path.join(output_dir, decoder_settings.system)
    os.makedirs(output_system_dir, exist_ok=True)
    with open(
        os.path.join(CONFIG.SYSTEMS_DIR, decoder_settings.system, 'config.yml'), 
        'r', encoding='utf-8'
    ) as infile:
        decode_config = yaml.safe_load(infile)
        orig_model_name = os.path.basename(decode_config['models'][0])
        orig_model = os.path.join(
            CONFIG.SYSTEMS_DIR, decoder_settings.system, orig_model_name)

    #this will be the new traindir in which we will finetune the model
    #everything will go into the output_dir/system_name (where the system_name
    #will be the same name as our original system, so the user only has to 
    #define SYSTEMS_DIR, and the code will use the same settings)
    this_outdir = os.path.join(output_dir, decoder_settings.system)

    #these will be the filepaths that we put in the various marian configs
    pretrained_model = os.path.join(this_outdir, 'pretrained.npz')
    finetuned_model = os.path.join(this_outdir, 'model.npz')

    #update the settings with the correct traindir that we'll run marian in
    decoder_settings = get_decoder_settings(
        src_lang, tgt_lang, 
        user_settings=user_settings, 
        extra_args=marian_args, 
        traindir=this_outdir
    )

    #copy the entire pretrained system (incl bpe models, vocabs, etc.)
    if os.path.exists(this_outdir) and not force:
        logger.info(f"Using previously existing {this_outdir} (use --force to destructively delete it and start over instead)")
    else:
        logger.info(f"Preparing system (copying to {this_outdir})...")
        shutil.rmtree(this_outdir)
        shutil.copytree(
            os.path.join(CONFIG.SYSTEMS_DIR, decoder_settings.system),
            this_outdir,
            dirs_exist_ok=True
        )
    
    #copy the pretrained model (more for recordkeeping purposes)    
    if os.path.exists(pretrained_model):
        logger.info(f"Using previously existing model for pretraining: {pretrained_model}")
    else:
        logger.info(f"Copying {orig_model} to {pretrained_model}")
        shutil.copy(orig_model, pretrained_model)

    #Remove spurrious \r, etc. which mess with line numbering
    logger.info(f"Preparing data (fixing fake line breaks)...")
    train_src, train_tgt = train_sets 
    valid_src, valid_tgt = valid_sets 
    cleaned_train_src, cleaned_train_tgt, train_length = clean_pair(
        this_outdir, train_src, train_tgt, 'train')
    cleaned_valid_src, cleaned_valid_tgt, valid_length = clean_pair(
        this_outdir, valid_src, valid_tgt, 'valid')

    #Use the TextProcessor on the data
    if os.path.exists(os.path.join(this_outdir, 'train.INPUT')) and not force:
        logger.info(f"Using previously generated {this_outdir}/train.* and {this_outdir}/valid.*")
    else:
        logger.info("Preprocessing data (moses, bpe, etc.)...")
        tp = decoder_settings.text_processor
        train_data = tp.prepare_training_data(
            this_outdir,
            src=cleaned_train_src,
            tgt=cleaned_train_tgt
        )
        valid_data = tp.prepare_training_data(
            this_outdir,
            src=cleaned_valid_src,
            tgt=cleaned_valid_tgt
        )
        #get the filenames in line with the names in the marian train config
        shutil.move(train_data['src'], os.path.join(this_outdir, 'train.INPUT'))
        shutil.move(train_data['tgt'], os.path.join(this_outdir, 'train.OUTPUT'))
        shutil.move(valid_data['src'], os.path.join(this_outdir, 'valid.INPUT'))
        shutil.move(valid_data['tgt'], os.path.join(this_outdir, 'valid.OUTPUT'))
        shutil.copyfile(valid_tgt, os.path.join(this_outdir, 'valid.REF'))

    #edit the train config to use our pretrained model (otherwise keep it the same)
    train_config = os.path.join(this_outdir, 'train.yml')
    logger.info(f"Creating train config {train_config}")
    with open(decoder_settings.train_config, 'r', encoding='utf-8') as infile, \
        open(train_config, 'w', encoding='utf-8') as outfile:
        marian_config = yaml.safe_load(infile)
        marian_config['pretrained-model'] = os.path.basename(pretrained_model)
        yaml.dump(marian_config, outfile)

    #copy decode config for later use; just change it to the finetuned model
    decode_config_file_1 = os.path.join(this_outdir, 'config.yml')
    decode_config_file_2 = os.path.join(this_outdir, 'config-fast.yml')
    logger.info(f"Creating decode configs {decode_config_file_1}")
    with open(decode_config_file_1, 'w', encoding='utf-8') as outfile1, \
         open(decode_config_file_2, 'w', encoding='utf-8') as outfile2:
        decode_config['models'] = [os.path.basename(finetuned_model)]
        yaml.dump(decode_config, outfile1)
        yaml.dump(decode_config, outfile2)

    #change directory because the marian train config has relative paths;
    #update the path of the config in the command to be just train.yml
    cwd = os.getcwd()
    os.chdir(this_outdir)
    idx = decoder_settings.cmd.index('-c') + 1
    decoder_settings.cmd[idx] = 'train.yml'

    #prepare the environment variables for the marian subprocess
    my_env = os.environ.copy()
    attrs = all_members(CONFIG)
    for attr in attrs:
        my_env[attr] = str(attrs[attr])

    cmd = ' '.join(decoder_settings.cmd)
    logger.info(f'IN {this_outdir}; RUNNING: {cmd}')

    if dry_run:
        logger.info(f"Dry run done.")
    else: 
        try:
            subprocess.check_output(cmd, stderr=sys.stderr, shell=True, env=my_env)
        except subprocess.CalledProcessError as e:
            return e.returncode
    
    os.chdir(cwd)
    logger.info(f"Finished training in {this_outdir}")

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=Formatter,
        description="Finetune an edinmt model using marian.",
        epilog=""
    )
    parser.add_argument('src_lang', help='source language')
    parser.add_argument('tgt_lang', help='target language')
    parser.add_argument('output_dir', 
        help="the output directory where to save new model and associated files")
    parser.add_argument('--train', required=True, nargs="+", 
        help="source and target training data")
    parser.add_argument('--valid', required=True, nargs="+", 
        help="source and target validation data")
    parser.add_argument('--system', default=CONFIG.SYSTEM,
        help='determines which included pretrained system to use (system configurations will be copied to output_dir/system)')
    parser.add_argument('--force', default=False, action='store_true',
        help='overwrite any existing fine-tuned directory; WARNING: the old data will be gone forever!')
    parser.add_argument('--dry-run', default=False, action='store_true',
        help='do everything except marian train')
    args, rest = parser.parse_known_args()
    args.rest = rest

    return args

if __name__ == '__main__':
    args = parse_args()
    main(
        src_lang=args.src_lang, 
        tgt_lang=args.tgt_lang, 
        output_dir=args.output_dir, 
        train_sets=args.train,
        valid_sets=args.valid,
        system_name=args.system,
        marian_args=args.rest,
        force=args.force,
        dry_run=args.dry_run,
    )