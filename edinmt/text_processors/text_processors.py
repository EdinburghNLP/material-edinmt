#!/usr/bin/env python3.7
# -*- coding: utf-8 -*
"""
The TextProcessor class is the interface pre-/post-processors must adhere 
to for translate.py to be able to use them correctly.  

Please implement this interface to aid in maintainability.

Other basic text_processors for single tools (e.g. SPM, SubwordNMT, Moses, etc.)
are implemented here. For text_processors that chain multiple steps together,
please see the edinmt.text_processors.composite_processors module.
"""
import logging
import math
import os
import pathlib
import shutil
import subprocess
from abc import ABC, abstractmethod
from functools import partial
from subprocess import PIPE, Popen, STDOUT
from typing import *

import sentencepiece as spm
from subword_nmt.apply_bpe import BPE, read_vocabulary

from edinmt import CONFIG 
from edinmt.configs.config import all_members
from edinmt.text_processors.norm.normalization import process as norm_process
from edinmt.utils import popen_communicate
from edinmt.parallely import pll_multi, pll_single

logger = logging.getLogger('edinmt.text_processors.text_processors')
logger.setLevel(CONFIG.LOG_LEVEL)
#only translation output should go on stdout so we remove StreamHandlers
handlers = logger.handlers.copy()
logger.handlers = [h for h in handlers if not isinstance(h, logging.StreamHandler)]

class TextProcessorException(BaseException):
    r"""Raise for errors in running text_processors."""

class TextProcessor():
    r"""
    Pre-/post-processes text prior (the step prior to sending to MT). Includes
    convenience functions to split long texts into multiple lines. Includes 
    basic implementations for handling files line-by-line. Subclasses can
    expand on these to make file processing more efficient than line-by-line. 
    Subclasses should aim to implement all the functions starting with 
    preprocess/postprocess.
    """
    def __init__(self, 
            src_lang: str, 
            tgt_lang: str, 
            parallel: Optional[bool]=True,
            ext: Optional[str]='.prep',
            **kwargs,
        ):
        #set up the attributes from the CONFIG, e.g. SYSTEMS_DIR, etc.
        settings = {
            x:y 
            for (x,y) in all_members(CONFIG).items() 
            if not x.startswith('__')
        }
        for k in settings:
            setattr(self, k, settings[k])

        #override settings from the CONFIG / add new settings from kwargs
        for k in kwargs:
            setattr(self, k, kwargs[k])

        #the arguments passed in directly should override anything prior
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.parallel = parallel
        self.ext = ext
        self.stream_log_fp = os.path.join(
            self.ROOT_DIR, 'text_processor_stderr.log')


    @staticmethod
    def wrap_text(text, max_length, before_wrap=None, after_wrap=None):
        """
        Split long lines into multiple lines of max_length number of tokens.
        before_wrap preprocesses before splitting, and after_wrap afterwards,
        e.g. BPE before wrapping and add multilingual tags after wrapping.
        """
        if before_wrap:
            text = before_wrap(text)
        split_text = text.split()
        length = len(split_text)
        start = 0
        end = max_length 
        new_text = ''
        times = 1
        if length > max_length: 
            times = math.ceil(length / max_length)
            for i in range(times):
                line = ' '.join(split_text[start:end])
                if after_wrap:
                    line = after_wrap(line)
                new_text = new_text + line + '\n' 
                start = end
                end = end + max_length
        elif after_wrap:                                              
            new_text = after_wrap(text).strip()
        else:
            new_text = text
        new_text = new_text.strip()
        return new_text, len(new_text.split('\n'))

    def preprocess(self, text: str) -> str:
        """Preprocess one line of text."""
        return text #noop returns unchanged text 

    def postprocess(self, text: str) -> str:
        """Postprocess one line of mt output text."""
        return text #noop returns unchanged text 

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        """Postprocess a file (base class does one line at a time)."""
        with open(input_fp, 'r', encoding='utf-8') as infile, \
             open(output_fp, 'w', encoding='utf-8') as outfile:
            for line in infile:
                line = line.strip()
                line = self.preprocess(line).strip()
                outfile.write(line + os.linesep)
        return output_fp

    def postprocess_file(self, input_fp: str, output_fp: str) -> str:
        """Postprocess a file (base class does one line at a time)."""
        with open(input_fp, 'r', encoding='utf-8') as infile, \
             open(output_fp, 'w', encoding='utf-8') as outfile:
            for line in infile:
                line = line.strip()
                line = self.postprocess(line).strip()
                outfile.write(line + os.linesep)
        return output_fp

    def preprocess_before_wrap(self, text: str) -> str:
        """
        Do preprocessing steps before splitting long lines,
        e.g. BPE the text so line splitting counts bpe tokens.
        """
        return self.preprocess(text) 

    def preprocess_after_wrap(self, text: str) -> str:
        """
        Do additional preprocessing on lines after they've been split 
        e.g. add multilingual tags to each line. (base class does nothing)
        """
        return text #noop returns unchanged text

    def preprocess_before_wrap_file(self, input_fp: str, output_fp: str) -> str:
        """Preprocess the file before splitting long lines."""
        return self.preprocess_file(input_fp, output_fp) 

    def preprocess_after_wrap_file(self, input_fp: str, output_fp: str) -> str:
        """
        Do additional preprocessing on lines after they've been split
        (base class just moves input_fp to the expected location at output_fp).
        """
        shutil.move(input_fp, output_fp)  
        return output_fp

    def wrap_and_preprocess(self, text: str) -> tuple:
        """Preprocess text and split a long line into multiple lines."""
        max_length = int(self.MAX_SENTENCE_LENGTH)
        wrapped, n = TextProcessor.wrap_text(
            text, 
            max_length, 
            self.preprocess_before_wrap, 
            self.preprocess_after_wrap
        )
        return wrapped, n

    def prepare_training_data(self, output_dir: str, src: str, tgt: str, **kwargs) -> list:
        r"""
        Prepare training data by preprocessing it with this text processor. 
        We must return output with {'src': src_file, 'tgt': tgt_file, ...} 
        See edinmt.cli.prepare_training_data
        """
        os.makedirs(output_dir, exist_ok=True)

        kwargs.update({'src': src, 'tgt': tgt})
        results = {}
        for k in kwargs:
            v = kwargs[k]
            if os.path.exists(v):
                out = os.path.join(output_dir, os.path.basename(v)) + self.ext
                out = self.preprocess_file(v, out)
                v = out
            results[k] = v 
        
        return results 


class MultilingualTextProcessor(TextProcessor):
    r"""Add multilingual tags to the start of the sentence."""
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        tag = f"<2{self.tgt_lang}>"
        return f"{tag} {text.strip()}"


class SpmTextProcessor(TextProcessor):
    r"""Byte-pair encode the text using SentencePiece BPE."""
    def __init__(self, src_lang, tgt_lang, bpe_model=None, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        if bpe_model:
            self.bpe_model = bpe_model
        else:
            self.bpe_model = os.path.join(
                self.SYSTEMS_DIR, 
                os.path.join(self.SYSTEM, "bpe.model")
            )

    def preprocess(self, text):
        s = spm.SentencePieceProcessor(model_file=self.bpe_model)
        result = s.encode(text, out_type=str, enable_sampling=False, alpha=0.1)
        result = ' '.join(result)
        return result

    def postprocess(self, text):
        #fast method from spm paper: https://arxiv.org/pdf/1808.06226.pdf
        text = text.strip().split() 
        text = ''.join(text).replace("▁", " ").strip() 
        return text

    def preprocess_file(self, input_fp, output_fp):
        command = [
            f"{self.SENTENCEPIECE_BUILD_DIR}/src/spm_encode",
            f"--model={self.bpe_model}",
            f"--output_format=piece",
            f"< {input_fp} > {output_fp}"
        ]
        cmd = ' '.join(command)
        logger.debug(f"RUNNING SPM APPLY BPE: {cmd}")
        subprocess.check_output(cmd, shell=True)
        return output_fp 
    
class MosesTokenizerTextProcessor(TextProcessor):
    r"""Space-tokenize and truecase the text using Moses."""
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        #NOTE: we always used 'en' as the detok language
        self.tgt_lang = 'en'

    def preprocess(self, text):
        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/tokenizer.perl", 
            "-a", "-l", f"{self.src_lang}", "-q",
        ]
        text = popen_communicate(cmd, text)

        return text

    def postprocess(self, text):
        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/detokenizer.perl",
            f"-threads {self.CPU_COUNT}",
            "-q", "-l", f"{self.tgt_lang}", "-q"
        ]
        text = popen_communicate(cmd, text) 

        return text

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        if self.parallel:
            cmd = [
                "perl", 
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/tokenizer.perl", 
                f"-threads {self.CPU_COUNT}",
                "-a", "-l", f"{self.src_lang}", "-q",
                f'< {input_fp} > {output_fp}'
            ]
        else:
            cmd = [
                "perl", 
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/tokenizer.perl", 
                "-a", "-l", f"{self.src_lang}", "-q",
                f'< {input_fp} > {output_fp}'
            ]

        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING MOSES TOKENIZER: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True) 

        return output_fp

    def postprocess_file(self, input_fp: str, output_fp: str) -> str:
        if self.parallel:
            cmd = [
                "perl", 
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/detokenizer.perl",
                f"-threads {self.CPU_COUNT}",
                "-q", "-l", f"{self.tgt_lang}", "-q",
                f"< {input_fp} > {output_fp}"
            ]
        else:
            cmd = [
                "perl", 
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/detokenizer.perl",
                "-q", "-l", f"{self.tgt_lang}", "-q",
                f"< {input_fp} > {output_fp}"
            ]
        logger.debug(f"RUNNING MOSES DETOKENIZER: {' '.join(cmd)}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(' '.join(cmd), stderr=outfile, shell=True) 
        return output_fp

class MosesTruecaserTextProcessor(TextProcessor):
    r"""Space-tokenize and truecase the text using Moses."""
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)

        self.src_truecaser = os.path.join(
            self.SYSTEMS_DIR, 
            os.path.join(self.SYSTEM, f"tc.{self.src_lang}")
        )

    def preprocess(self, text):
        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/recaser/truecase.perl", 
            f"--model", f"{self.src_truecaser}"
        ]
        text = popen_communicate(cmd, text) 

        return text

    def postprocess(self, text):
        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/recaser/detruecase.perl", 
        ]
        text = popen_communicate(cmd, text)

        return text

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        #NOTE: we don't use gnu parallel here because loading the truecase 
        #model is the slow part, but it could be done with:
        # cat {input_fp} | parallel --jobs {n} --pipe --recend '' -k 'perl ...' > {output_fp}
        cmd = [
            f"perl",
            f"{self.MOSESSCRIPTS_DIR}/scripts/recaser/truecase.perl", 
            f"--model", f"{self.src_truecaser}",
            f"< {input_fp} ",
            f"> {output_fp}",
        ]
        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING MOSES TRUECASE: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True) 
        return output_fp

    def postprocess_file(self, input_fp: str, output_fp: str) -> str:
        cmd = [
            f"perl",
            f"perl {self.MOSESSCRIPTS_DIR}/scripts/recaser/detruecase.perl", 
            f"< {input_fp} ",
            f"> {output_fp}",
        ]
        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING MOSES DETRUECASE: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True) 
        return output_fp


class SubwordNmtTextProcessor(TextProcessor):
    r"""Byte-pair encode the text using Subword-NMT BPE."""
    LEGACY_SYSTEMS_VOCAB_THRESHOLDS = {
        "ensw": 50,
        "swen": 50,
        "soen": 5,
        "enso": 5,
        "spen": 5,
        "ensp": 5,
        "lten": 5, 
        "enlt": 5, 
    }
    #default names were {src_lang}{tgt_lang}.bpe but these are exceptions
    LEGACY_SYSTEMS_BPE_MODELS = {
        "psen": "bpe.{src_lang}",
        "enps": "bpe.{src_lang}",
    }

    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.path = os.path.join(
            self.TOOLS_DIR,
            'subword-nmt', 'subword_nmt', 'apply_bpe.py'
        )

        k = f"{self.src_lang}{self.tgt_lang}"

        self.bpe_model = os.path.join(
            self.SYSTEMS_DIR, 
            self.SYSTEM, 
            f"{k}.bpe"
        )
        #dropout should only be used for training data
        self.dropout = 0.0

        #Some systems used a weird naming scheme that we have to adapt to
        if k in self.LEGACY_SYSTEMS_BPE_MODELS:
            self.bpe_model = os.path.join(
                self.SYSTEMS_DIR,
                self.SYSTEM,
                self.LEGACY_SYSTEMS_BPE_MODELS[k].format(src_lang=src_lang)
            )

        #In case we use a vocab file, we have to do a few extra steps 
        #to prepare subword-nmt which are done in that package's main 
        self.vocab_file, self.thresh = None, None
        vocab = None
        if k in self.LEGACY_SYSTEMS_VOCAB_THRESHOLDS: 
            self.thresh = self.LEGACY_SYSTEMS_VOCAB_THRESHOLDS[k]
            #tgt_vocab_file == src_vocab_file because of shared BPE model
            self.vocab_file = os.path.join(
                self.SYSTEMS_DIR, 
                self.SYSTEM,
                f"vocab.{src_lang}"
            )
            logger.debug(f"Using vocab_file: {self.vocab_file}")
            with open(self.vocab_file, 'r', encoding='utf-8') as infile:
                vocab = read_vocabulary(infile, threshold=self.thresh)

        with open(self.bpe_model, 'r', encoding='utf-8') as infile:
            self.bpe = BPE(infile, vocab=vocab)

    def preprocess(self, text):
        return self.bpe.process_line(text, self.dropout)

    def postprocess(self, text):
        return text.replace('@@ ', '')

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        if self.vocab_file:
            cmd = [
                f"python3 {self.path} -c {self.bpe_model}",
                f"--vocabulary {self.vocab_file}",
                f"--vocabulary-threshold {self.thresh}",
                f"--dropout {self.dropout}",
                f"--input {input_fp}",
                f"--output {output_fp}"
            ]
        else:
            cmd = [
                f"python3 {self.path} -c {self.bpe_model}",
                f"--dropout {self.dropout}",
                f"--input {input_fp}",
                f"--output {output_fp}"
            ]
        if self.parallel:
            cmd.append(f'--num-workers {self.CPU_COUNT}')
        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING SUBWORD-NMT BPE: {cmd}")
        subprocess.check_output(cmd, shell=True)
        return output_fp

    def postprocess_file(self, input_fp: str, output_fp: str) -> str:
        cmd = f"sed -e 's/(@@ )|(@@ ?$)//g' {input_fp} > {output_fp}"
        logger.debug(f"RUNNING SUBWORD-NMT DE-BPE: {cmd}")
        subprocess.check_output(cmd, shell=True)
        return output_fp

class NormTextProcessor(TextProcessor):
    r"""Normalize the text using language-specific rules."""

    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        mapping = {
            'en': 'ENG',
            'sw': 'SWA',
            'tl': 'TGL',
            'so': 'SOM',
            'lt': 'LIT',
            'bg': 'BUL',
            'ps': 'PUS',
            'kk': 'KAZ',
            'ka': 'KAT',
        }

        self.mapped_src_lang = None
        if self.src_lang in mapping:
            self.mapped_src_lang = mapping[self.src_lang]
        self.mapped_tgt_lang = None
        if self.tgt_lang in mapping:
            self.mapped_tgt_lang = mapping[self.tgt_lang]

    def preprocess(self, text):
        text = norm_process(
            self.mapped_src_lang, 
            text, 
            copy_through=True, 
            keep_romanized_text=True
        )
        return text

    def postprocess(self, text):
        text = norm_process(self.mapped_tgt_lang, text)
        return text

    @staticmethod
    def norm_process_file(input_fp, output_dir, lang, **kwargs):
        output_fp = os.path.join(output_dir, os.path.basename(input_fp))
        with open(input_fp, 'r', encoding='utf-8') as infile, \
             open(output_fp, 'w', encoding='utf-8') as outfile:
            for line in infile:
                line = norm_process(lang, line, **kwargs).strip()
                outfile.write(line + '\n')
        return output_fp

class QueryAppendedTextProcessor(TextProcessor):
    r"""
    Take tab-separated sentence and query data, and reformat it
    into the format the model expects for query-guided MT. Our
    baseline model used a ||| delimiter between sentence an query.
    """
    INPUT_DELIM = '\t'
    OUTPUT_DELIM = ' ||| '

    def preprocess(self, text):
        if self.INPUT_DELIM in text:
            sentence, query = text.split(self.INPUT_DELIM, maxsplit=1)
            text = f"{sentence.strip()}{self.OUTPUT_DELIM}{query.strip()}"
        return text
    
    def preprocess_file(self, input_fp, output_fp):
        cmd = f'sed -e "s/{self.INPUT_DELIM}/{self.OUTPUT_DELIM}/g" {input_fp} > {output_fp}'
        logger.debug(f"RUNNING QUERY APPEND: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True)
        return output_fp

class MosesNormPunctTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}", 
        ]
        text = popen_communicate(cmd, text) 
        return text

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        r"""
        Preprocess using moses normalize-punctuation.
        """
        if self.parallel:
            cmd = [
                f"cat {input_fp} | ",
                f"parallel --jobs {self.CPU_COUNT} --pipe --recend '' -k '",
                f"perl",
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}",
                f"'" 
                f"> {output_fp}",
            ]
        else:
            cmd = [
                f"perl",
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}",
                f"< {input_fp} > {output_fp}",
            ]
        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING MOSES NORM PUNCT: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True) 
        return output_fp


class RemovePunctTextProcessor(NormTextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        r"""First use reksander's script, then moses to remove punctuation."""
        text = norm_process(self.src_lang, text, remove_punct=True).strip()

        cmd = [
            "perl", 
            f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}", 
        ]
        text = popen_communicate(cmd, text) 
        return text

    def postprocess(self, text):
        r"""Override super's postprocess with no-op."""
        return text

    def preprocess_file(self, input_fp: str, output_fp: str) -> str:
        r"""
        Multiprocess the input_fp using Reksander's normalization scripts, 
        then again using moses normalize-punctuation, to remove punctuation.
        """
        part = partial(
            NormTextProcessor.norm_process_file, 
            output_dir=os.path.dirname(output_fp),
            lang=self.src_lang,
            remove_punct=True,
        )
        logger.debug(f"RUNNING SCRIPTS NORM: {input_fp}")
        normed_fp = pll_single(
            input_fp, 
            part, 
            n_jobs=CONFIG.CPU_COUNT, 
            outdir=os.path.dirname(output_fp), 
            output_name=os.path.basename(input_fp) + '.norm'
        )

        if self.parallel:
            cmd = [
                f"cat {normed_fp} | ",
                f"parallel --jobs {self.CPU_COUNT} --pipe --recend '' -k '",
                f"perl",
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}",
                f"'" 
                f"> {output_fp}",
            ]
        else:
            cmd = [
                f"perl",
                f"{self.MOSESSCRIPTS_DIR}/scripts/tokenizer/normalize-punctuation.perl -l {self.src_lang}",
                f"< {input_fp} > {output_fp}",
            ]
        cmd = ' '.join(cmd).strip()
        logger.debug(f"RUNNING MOSES NORM PUNCT: {cmd}")
        with open(self.stream_log_fp, 'a', encoding='utf-8') as outfile:
            subprocess.check_output(cmd, stderr=outfile, shell=True) 
        return output_fp
