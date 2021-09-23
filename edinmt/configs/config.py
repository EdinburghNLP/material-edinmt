#!/usr/bin/env python3.7
# -*- coding: utf-8 -*
"""
The Config defining filepaths and settings for tools.

Note that in the Docker system, tools will end up at the locations defined
in the edinmt/Makefile, which in turn reads from edinmt/configs/env_build.sh,
and settings for running this system will be assigned from the 
edinmt/configs/env_run.sh. When running locally (outside of Docker), you will
want to set or export the environment variables for your local environment,
in particular, you will need to set the paths for marian and tools.
"""
import logging
import math
import multiprocessing
import os
import pathlib
import socket

LOCALHOST = socket.gethostbyname(socket.gethostname())

def is_truthy(value):
    """Convert falsey values to actual False and all others to True."""
    if value in [False, 0, '0', 'false', 'False', 'no', 'No', 'NO']:
        return False
    return True

class Config(object):
    LOG_LEVEL = logging.INFO

    #Directory where all of the code resides (typically /mt in Docker)
    ROOT_DIR = os.getenv('ROOT_DIR', '/mt').strip()

    #Directory where MT models are downloaded; used to launch marian-server
    SYSTEMS_DIR = os.getenv('SYSTEMS_DIR', os.path.join(ROOT_DIR, 'systems')).strip()

    #We need the system name to find the correct folder for the specific
    #model in the systems dir; often, this will be {src}{tgt} but that 
    #naming scheme isn't guaranteed so we leave it as a config option
    SYSTEM = os.getenv('SYSTEM', None)

    #SRC/TGT can be used to infer the SYSTEM instead (perferred by users) 
    SRC = os.getenv('SRC', None)
    TGT = os.getenv('TGT', None)

    #For those systems whose lang combos are not immediately inferred from
    #their name (e.g. 'faen' would be ('fa', 'en')), we add a mapping; we use
    #this to look up systems when the user provides SRC/TGT but no SYSTEM
    #and when a dedicated unidirectional system is apparently not available
    #TODO models to include a description that contains all their features
    #instead of maintaining all these separate mappings
    SYSTEM_TO_LANGS = {
        'kkenru': [('kk', 'en'), ('en', 'kk'), ('kk', 'ru'), ('ru', 'kk'), ('en', 'ru'), ('ru', 'en')]
    }

    #Downstream user wants us to automatically swap to "audio" models (i.e.
    #models trained on lowercased data) without providing the real system name.
    #For some of those models, we historically kludged their language names,
    #so we have to add an additional lookups for that now, e.g.:
    #faen + audio = fsen system and fsen system langs are fs & en
    #TODO fix the names of those and remove audio_systems_to_langs map
    TYPE = os.getenv('TYPE', None)
    AUDIO_TYPE_SYSTEMS_MAP = { 
        'faen': 'fsen',
        'soen': 'spen',
        'kken': 'kken_no_punct',
        'kaen': 'kaen_no_punct'
    }
    AUDIO_SYSTEMS_TO_LANGS = {
        'fsen': ('fs', 'en'), #originally fa2en but bpe etc uses these names
        'spen': ('sp', 'en'), #originally so2en but bpe etc uses these names
    }

    #Some systems are designed to be used with query guided translation and we
    #select the system so user doesn't have to provide the correct system name
    QUERY = is_truthy(os.getenv('QUERY', False))
    QUERY_TYPE_SYSTEMS_MAP = {
        'kken': 'kken_query',
        'kaen': 'kaen_query'
    }

    #Downstream user wants a "fast" model, in which case we avoid using our 
    #more accurate ensemble; this is actually controlled in the marian config 
    MODE = os.getenv("MODE", "DEFAULT").strip()
    MODE_TO_MARIAN_CONFIG = {
        'DEFAULT': 'config.yml',
        'accurate': 'config.yml',  #slow but higher quality ensemble of 4 models
        'fast': 'config-fast.yml', #fast but lower quality single model 
    }

    #NBEST==True means get n-best sentences (n=beam-size from marian config)
    #NBEST==False means return the 1 best
    NBEST = is_truthy(os.getenv("NBEST", False))

    #NBEST_WORDS==True means marian-decoder gives us the n-best tokens in 
    #each position in the sentence; we have to use Alham's marian-decoder:
    #https://github.com/afaji/Marian/tree/alt-words
    NBEST_WORDS = is_truthy(os.getenv("NBEST_WORDS", False))
    NBEST_WORDS_BUILD_DIR = pathlib.Path(
        os.getenv('NBEST_WORDS_BUILD_DIR', f'{ROOT_DIR}/marian-nbest-words/build/')
    ).resolve().as_posix()

    #Pre-/post-processors to use for processing text before sending to decoder
    SYSTEM_TO_TEXT_PROCESSOR = {
        'DEFAULT': 'MosesSubwordNmtTextProcessor',
        'enps': 'NormSubwordNmtTextProcessor', 
        'psen': 'NormSubwordNmtTextProcessor', 
        'kkenru': "MultilingualSpmTextProcessor",
        'kken_query': "QueryMosesSubwordNmtTextProcessor",
        'kken_no_punct': "RemovePunctMosesSubwordNmtTextProcessor",
        'kken': "MosesNormPunctMosesSubwordNmtTextProcessor",
        'enkk': "MosesNormPunctMosesSubwordNmtTextProcessor",
        'kaen': "SpmTextProcessor",
        'enka': "SpmTextProcessor",
        'kaen_query': 'QuerySpmTextProcessor',
        'kaen_no_punct': "RemovePunctMosesSubwordNmtTextProcessor",
    }

    #Some systems are designed to passthrough urls/emails/tags/etc. wholesale,
    #but we need extra code to extract and re-insert them, so we need to know
    #if this is one such system 
    PASSTHROUGH_SYSTEMS = set([
        'kaen',
        'enka',
        'kaen_query',
    ])

    #the GPUs to use; None means CPU will be used
    DEVICES = os.getenv('DEVICES', None)

    #the CPUs to use if not using GPU; half of available CPUs by default
    CPU_COUNT = os.getenv('CPU_COUNT', 
        max(1, math.floor(multiprocessing.cpu_count() / 2) - 1))

    #Directory where marian was built, containing marian-server executable
    MARIAN_BUILD_DIR = pathlib.Path(
        os.getenv('MARIAN_BUILD_DIR', f'{ROOT_DIR}/marian-dev/build/')
    ).resolve().as_posix()

    #Directory for additional tools like Moses, SPM, etc.
    TOOLS_DIR = os.getenv('TOOLS_DIR', os.path.join(ROOT_DIR, 'tools'))

    #Sentencepiece (SPM) byte-pair encoding (BPE) library
    SENTENCEPIECE_BUILD_DIR = pathlib.Path(
        os.getenv('SENTENCEPIECE_BUILD_DIR', f"{TOOLS_DIR}/sentencepiece/build")
    ).resolve().as_posix()

    #Moses text processing scripts, e.g. space-tokenizer, truecaser, etc.
    MOSESSCRIPTS_DIR = pathlib.Path(
        os.getenv('MOSESSCRIPTS_DIR', f"{TOOLS_DIR}/moses-scripts/") 
    ).resolve().as_posix()

    #Very long lines can cause CUDA OOM so we need to handle them; we can do
    #this using either marian's built-in "--max-length X --max-length-crop"
    #or by wrapping the long lines ourselves 
    MAX_SENTENCE_LENGTH = int(os.getenv('MAX_SENTENCE_LENGTH', 200))

    #the port for the marian-server; servers launched in Docker using `serve`
    MARIAN_PORT = os.getenv('MARIAN_PORT', 8080)

    #Configs used for launching the pipeline server that sends/receives
    #requests to marian-server after pre-/post- processing the inputs.
    MARIAN = os.getenv('MARIAN', f'ws://{LOCALHOST}:{MARIAN_PORT}')
    PIPELINE_PORT = os.getenv('PIPELINE_PORT', 8081)
    PIPELINE_HOST = os.getenv('PIPELINE_HOST', '0.0.0.0').strip()

    #json-lines, marian e.g. "0 ||| sent0" or plaintext, e.g. "sent0"
    FMTS = ['json', 'marian', 'text'] 
    FMT = os.getenv('FMT', 'json') #default output format is json-lines

    #delete temporary files/dirs, extra logs, etc.
    PURGE = is_truthy(os.getenv('PURGE', False))
    DEBUG = is_truthy(os.getenv('DEBUG', False)) 

    #allow instances of config to be updated from keyword args on the fly;
    #useful for changing runtime settings from user inputs instead of using
    #pre-defined environment variable settings 
    def __init__(self, **kwargs):
        [setattr(self, k, kwargs[k]) for k in kwargs]
    

class TestConfig(Config):
    r"""
    Configs specifically for testing or debugging. Overrides Config settings.
    """
    LOG_LEVEL = logging.DEBUG
    #delete temporary files/dirs, extra logs, etc.
    PURGE = is_truthy(os.getenv('PURGE', False)) 
    DEBUG = is_truthy(os.getenv('DEBUG', True)) 


def all_members(aClass):
    """
    Return all of the members of a class as a dict, including its superclass
    members. Useful for getting inherited config settings as a dict.

    Acknowledgements:
    https://www.oreilly.com/library/view/python-cookbook/0596001673/ch05s03.html
    """
    try:
        # Try getting all relevant classes in method-resolution order
        mro = list(aClass.__mro__)
    except AttributeError:
        # If a class has no __mro__, then it's a classic class
        def getmro(aClass, recurse):
            mro = [aClass]
            for base in aClass.__bases__: mro.extend(recurse(base, recurse))
            return mro
        mro = getmro(aClass, getmro)
    mro.reverse()
    members = {}
    for someClass in mro: members.update(vars(someClass))
    return members