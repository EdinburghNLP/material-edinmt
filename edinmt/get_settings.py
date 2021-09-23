r"""
In this module, we reconcile the environment variables with the user settings
and the marian config file settings.

Arg hierarchy should be as follows, with later args overriding earlier ones:
our defaults < os environment < marian config file < cli user inputs

The user settings typically come from the command-line scripts in edinmt/cli/
but may also come from tests or anywhere else, where we need to set up the 
subprocess command to invoke marian-decoder with the correct user arguments.

The user settings should be a dict of the same keys as in our config, see
edinmt/configs/config.py, so that we can use it to override the config.
"""
#TODO: Can we simplify all of this somehow, maybe switch to pydantic?

import logging
import os
import pathlib
import shutil
from collections import namedtuple

import yaml

from edinmt import CONFIG
from edinmt.configs.config import all_members
from edinmt.text_processors import TEXT_PROCESSORS

logger = logging.getLogger(__name__)
logger.setLevel(CONFIG.LOG_LEVEL)


def get_decoder_settings(
        src_lang=None, 
        tgt_lang=None, 
        config=CONFIG, 
        user_settings=None, 
        extra_args=None, 
        server=False,
        traindir=False
    ):
    r"""
    Get the subprocess cmd and additional arguments to run translation using
    marian-decoder or marian-server from the config and the user settings.

    Args:
        src_lang: source language to translate from
        tgt_lang: target language to translate into
        config: see edinmt.configs.config.Config
        user_settings: a dict to override config with 
        extra_args: any command line arguments the user included
        server: True to make cmd for marian-server (instead of marian-decoder)
        traindir: dir where fine-tuning data is, makes cmd for marian train

    Returns:
        DecoderSettings, a namedtuple object with fields for:
            cmd: full marian command to invoke, including marian path and args 
            text_processor: TextProcessor object to give the translator 
            batch_size: mini-batch from marian config 
            max_sent_length: maximum sentence length parameter to fit on gpu
            n_best: beam-sie from marian config 
            n_best_words: True if marian decoder is Alham's n-best-words one
            fmt: True if the user wants json-lines output
            extract_tags: True if this model uses passthrough for URLs etc.,
            system: the name of the system we are using

    NOTE: There's a lot of complexity here, because downstream users prefer to
    input args through env variables at times and on the cli at other times.
    This method tries to reconcile all the possible entry methods to get the
    final arguments we need to run our own servers and marian-decoder.
    TODO: This whole thing needs a well thought-out refactor
    """
    DecoderSettings = namedtuple(
        'DecoderSettings', 
        [
            'cmd', 
            'text_processor', 
            'batch_size', 
            'max_sent_length',
            'n_best',
            'n_best_words', 
            'fmt',
            'extract_tags',
            'system',
            'marian_config',
            'train_config',
            'validate_sh',
        ]
    )
    #1. create a settings dictionary for all the other functions to use
    settings = {x:y for (x,y) in all_members(config).items() if not x.startswith('__')}
    if user_settings:
        settings.update(user_settings)

    #2. we need to get the src_lang and tgt_lang from somewhere, so we know
    #   which system to load; function args override config and user_settings 
    if src_lang and tgt_lang:
        settings.update({'SRC': src_lang, 'TGT': tgt_lang})
    if 'SRC' not in settings or 'TGT' not in settings:
        raise KeyError("Source/target languages not found. Please use SRC/TGT environment variables.")

    #3. try to infer system from the lang combo (audio type is also checked)
    system = _find_system(settings=settings)
    settings['SYSTEM'] = system

    #4. search for marian-decoder or marian-server from the build dir
    marian = _find_marian(settings=settings, server=server, traindir=traindir)

    #5. reconcile env variables with user settings and possible marian args
    #   also find some marian settings that the pipeline will also need to know
    collected = _collect_marian_args(settings=settings, extra_args=extra_args, traindir=traindir)
    settings['MAX_SENTENCE_LENGTH'] = collected[2]

    #6. find the text processor from the language combo and system dirs
    #   For some of these models, we ended up kludging their src/tgt in the
    #   past to account for audio modes, so we have to undo this here using
    #   another lookup, so that the text_processor has the correct langs
    src_lang, tgt_lang = _find_audio_type_langs(settings=settings)
    text_processor = None
    if src_lang and tgt_lang:
        text_processor = _get_text_processor(src_lang, tgt_lang, settings)

    #7. build up the command that we'll invoke in the subprocess
    cmd = []
    cmd.append(marian)
    cmd.extend(collected[0])

    #find additional config and training files (for finetuning if needed)
    marian_config, train_config, validate_sh = _find_marian_config(
        settings, traindir)

    decoder_settings = DecoderSettings(
        cmd=cmd,
        text_processor=text_processor,
        batch_size=collected[1],
        max_sent_length=collected[2],
        n_best=collected[3],
        n_best_words=collected[4],
        fmt=collected[5],
        extract_tags=system in settings['PASSTHROUGH_SYSTEMS'],
        system=system,
        marian_config=marian_config,
        train_config=train_config,
        validate_sh=validate_sh,
    )

    return decoder_settings 

def _get_text_processor(src_lang, tgt_lang, settings):
    r"""Instantiate a text pre-/post-text_processor that's used on each sentence."""
    if settings['SYSTEM'] is None:
        settings['SYSTEM'] = f"{src_lang}{tgt_lang}"

    if settings['SYSTEM'] in settings['SYSTEM_TO_TEXT_PROCESSOR']:
        name = settings['SYSTEM_TO_TEXT_PROCESSOR'][settings['SYSTEM']]
    else:
        name = settings['SYSTEM_TO_TEXT_PROCESSOR']['DEFAULT']

    try:
        text_processor = TEXT_PROCESSORS[name](src_lang, tgt_lang, **settings)
    except:
        logger.error(f"Error loading text processor {name}: {src_lang} {tgt_lang} {settings}")
        raise
    else:
        logger.debug(f"Using text pre- and post-processing: {name}: {src_lang} {tgt_lang}")

    return text_processor

def _find_audio_type_langs(settings):
    r"""Some 'audio' systems had their names kludged, so we need to undo that now."""
    if settings['TYPE'] == 'audio' and settings['SYSTEM'] in settings['AUDIO_SYSTEMS_TO_LANGS']:
        src_lang, tgt_lang = settings['AUDIO_SYSTEMS_TO_LANGS'][settings['SYSTEM']]
    else:
        src_lang = settings['SRC']
        tgt_lang = settings['TGT']
    return src_lang, tgt_lang

def _find_system(settings):
    r"""Infer the system based on the SRC/TGT lang in the settings."""
    systems = os.listdir(settings['SYSTEMS_DIR'])

    target_system = settings['SYSTEM']
    if not target_system:
        target_system = f"{settings['SRC']}{settings['TGT']}"

    if settings['TYPE'] == 'audio':
        if target_system in settings['AUDIO_TYPE_SYSTEMS_MAP']:
            target_system = settings['AUDIO_TYPE_SYSTEMS_MAP'][target_system]
    if settings['QUERY']:
        if target_system in settings['QUERY_TYPE_SYSTEMS_MAP']:
            target_system = settings['QUERY_TYPE_SYSTEMS_MAP'][target_system]

    #maybe we can still recognize the system from the language direction
    if target_system not in systems:
        possibilities = []

        for k in settings['SYSTEM_TO_LANGS']:
            directions = settings['SYSTEM_TO_LANGS'][k]
            for tup in directions:
                if f"{tup[0]}{tup[1]}" == target_system:
                    possibilities.append(k)

        if len(possibilities) > 1:
            msg = f"Multiple possible systems for lang combo. Please use SYSTEM env variable or --system flag to select specific system, choose from: {possibilities}"
            logger.error(msg)
            logger.debug(f"SETTINGS: {settings}")
            raise KeyError(msg)
        elif len(possibilities) == 0:
            msg = f"Unrecognized system: {target_system}; expected one of {systems}"
            logger.error(msg)
            logger.debug(f"SETTINGS: {settings}")
            raise KeyError(msg)
        else:
            target_system = possibilities[0]

    return target_system

def _find_marian(settings, server=False, traindir=False):
    r"""Find where the marian-decoder/marian-server executable is located."""
    if settings['NBEST_WORDS']:
        marian_build_dir = settings['NBEST_WORDS_BUILD_DIR']
    else:
        marian_build_dir = settings['MARIAN_BUILD_DIR']

    if not os.path.isdir(marian_build_dir):
        msg = f"Not a directory; marian not found: {marian_build_dir}"
        logger.error(msg)
        logger.debug(f"SETTINGS: {settings}")
        raise NotADirectoryError(msg)

    if server:
        marian = os.path.join(marian_build_dir, 'marian-server')
    if traindir:
        marian = os.path.join(marian_build_dir, 'marian')
    else:
        marian = os.path.join(marian_build_dir, 'marian-decoder')

    if not os.path.exists(marian):
        msg = f"marian not found: {marian}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    return marian

def _find_marian_config(settings: dict, traindir=False):
    r"""Read configs to find the correct filepath of the marian config.yml"""
    if settings['SYSTEMS_DIR'] is None:
        msg = "Location of MT systems (SYSTEMS_DIR) not set."
        logger.error(msg)
        logger.debug(f"SETTINGS: {settings}")
        raise KeyError(msg)

    model_dir = os.path.join(settings['SYSTEMS_DIR'], settings['SYSTEM'])
    if not os.path.isdir(model_dir):
        msg = f"Not a directory; model not found (did you set the SYSTEM?): {model_dir}"
        logger.error(msg)
        logger.debug(f"SETTINGS: {settings}")
        raise NotADirectoryError(msg)

    if settings['MODE'] is None:
        settings['MODE'] = 'DEFAULT'

    config_filename = settings['MODE_TO_MARIAN_CONFIG'][settings['MODE']] 
    marian_config_path = os.path.join(model_dir, config_filename)

    #additionally, copy default train config and validate.sh files for finetuning
    train_config, validate_sh = None, None
    if traindir:
        train_config = os.path.join(model_dir, 'train.yml')
        validate_sh = os.path.join(model_dir, 'validate.sh')
        if not os.path.exists(train_config):
            marian_config_templ = os.path.join(settings['ROOT_DIR'], 'edinmt', 'configs', 'train.DEFAULT.yml')
            shutil.copyfile(marian_config_templ, train_config)
        validate_sh = os.path.join(model_dir, 'validate.sh')
        if not os.path.exists(validate_sh):
            validate_templ = os.path.join(settings['ROOT_DIR'], 'edinmt', 'configs', 'validate_DEFAULT.sh')
            shutil.copyfile(validate_templ, validate_sh)

    if not os.path.exists(marian_config_path):
        msg = f"Marian config not found: {marian_config_path}"
        logger.error(msg)
        logger.debug(f"SETTINGS: {settings}")
        raise FileNotFoundError(msg)
        
    return marian_config_path, train_config, validate_sh
    
def _collect_marian_args(settings, extra_args=None, traindir=None):
    r"""
    Read from environment configs, marian config and user-provided extra_args,
    to build up the entire list of arguments that we will pass to marian.
    """
    if extra_args is None:
        extra_args = []
    else:
        extra_args = extra_args.copy() #so we don't append to master list

    n_best_words = settings['NBEST_WORDS']
    fmt = settings['FMT']

    #find config
    if '-c' in extra_args: 
        marian_config_path = extra_args[extra_args.index('-c') + 1]
    elif '--config' in extra_args: 
        marian_config_path = extra_args[extra_args.index('--config') + 1]
    else:
        marian_config_path, train_config, validate_sh = _find_marian_config(
            settings=settings, traindir=traindir)
        extra_args.append('-c')
        if traindir:
            extra_args.append(train_config)
        else:
            extra_args.append(marian_config_path)

    #read some values directly from marian config 
    with open(marian_config_path, 'r', encoding='utf-8') as infile:
        marian_config = yaml.safe_load(infile) 
    beam_size = int(marian_config['beam-size'])
    batch_size = None
    max_sent_length = None
    if 'mini-batch' in marian_config:
        batch_size = int(marian_config['mini-batch'])

    #this is to figure out how to best split sentences across lines
    if 'max-length' in marian_config:
        max_sent_length = int(marian_config['max-length'])
    elif 'mini-batch-words' in marian_config:
        max_sent_length = int(marian_config['mini-batch-words'])
    if '--max-length' in extra_args:
        max_sent_length = int(
            extra_args[extra_args.index('--max-length') + 1]
        )
    elif '--mini-batch-words' in extra_args and 'max-length' not in marian_config:
        max_sent_length = int(
            extra_args[extra_args.index('--mini-batch-words') + 1]
        )
    if max_sent_length is None: #only if we didn't find it yet
        max_sent_length = settings['MAX_SENTENCE_LENGTH']

    #if the user selected to use n-best, set it to beam size for this model
    n_best = 1
    if settings['NBEST'] or '--n-best' in extra_args: 
        n_best = beam_size
    #if the user configured n-best but it's not in marian args yet, add it
    if n_best > 1 and '--n-best' not in extra_args:
        extra_args.append('--n-best')

    #find devices or fall back to using CPU
    devices = settings['DEVICES']
    if devices and '--devices' not in extra_args:
        extra_args.append('--devices')
        if isinstance(devices, list):
            devices = ' '.join(devices)
        extra_args.append(devices)
    elif '--devices' not in extra_args and '--cpu-threads' not in extra_args:
        extra_args.append('--cpu-threads')
        extra_args.append(str(settings['CPU_COUNT']))
    #some users prefer '0,1,2,3' format, but marian only accepts '0 1 2 3'
    if '--devices' in extra_args: 
        idx = extra_args.index('--devices') + 1
        devices = extra_args[idx]
        devices.replace('"', '')
        devices.replace("'", '')
        devices = devices.replace(',', ' ')
        extra_args[idx] = devices

    extra_args = [str(x) for x in extra_args]

    return (extra_args, batch_size, max_sent_length, n_best, n_best_words, fmt)
