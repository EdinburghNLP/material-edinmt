#!/usr/bin/env python3.7
# -*- coding: utf-8 -*
import os
import subprocess
from subprocess import PIPE, Popen, STDOUT
from typing import *

from edinmt import CONFIG
from edinmt.text_processors.text_processors import * 

logger = logging.getLogger('edinmt.text_processors.composite_processors')
logger.setLevel(CONFIG.LOG_LEVEL)
#only translation output should go on stdout so we remove StreamHandlers
handlers = logger.handlers.copy()
logger.handlers = [h for h in handlers if not isinstance(h, logging.StreamHandler)]

class MultilingualSpmTextProcessor(TextProcessor):
    """First add multilingual tag, then BPE."""
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.mult = MultilingualTextProcessor(src_lang, tgt_lang, **kwargs)
        self.bper = SpmTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.mult.preprocess(text).strip()
        text = self.bper.preprocess(text).strip()
        return text

    def postprocess(self, text):
        return self.bper.postprocess(text)

    def preprocess_file(self, input_fp, output_fp):
        fp = self.mult.preprocess_file(input_fp, input_fp + '.mult')
        fp = self.bper.preprocess_file(fp, output_fp)
        return output_fp

    def postprocess_file(self, input_fp, output_fp):
        return self.bper.postprocess_file(input_fp, output_fp)

    def preprocess_before_wrap(self, text):
        return self.bper.preprocess(text).strip()

    def preprocess_after_wrap(self, text):
        text = text.strip()
        new_text = ''
        for line in text.split(os.linesep):
            #NOTE: for backwards compatibility, we have to add the ▁ at 
            #the start because that's how spm would bpe the tag, since we
            #trained on tagged sources when using this text processor
            line = f'▁ {self.mult.preprocess(line).strip()}'
            new_text += line + os.linesep
        return new_text.strip()

    def preprocess_before_wrap_file(self, input_fp, output_fp):
        return self.bper.preprocess_file(input_fp, output_fp)
    
    def preprocess_after_wrap_file(self, input_fp, output_fp):
        with open(input_fp, 'r', encoding='utf-8') as infile, \
             open(output_fp, 'w', encoding='utf-8') as outfile:
            for line in infile:
                line = self.preprocess_after_wrap(line)
                outfile.write(line)
        return outfile 

    def prepare_training_data(self, output_dir: str, src: str, tgt: str, **kwargs) -> list:
        r"""
        Prepare training data by preprocessing it with this text processor. 
        We must return output with {'src': src_file, 'tgt': tgt_file, ...} 
        See edinmt.cli.prepare_training_data
        """
        os.makedirs(output_dir, exist_ok=True)

        src_out = os.path.join(output_dir, os.path.basename(src)) + self.ext
        src_out = self.preprocess_file(src, src_out)
        tgt_out = os.path.join(output_dir, os.path.basename(tgt)) + self.ext
        tgt_out = self.bper.preprocess_file(tgt, tgt_out)
        results = kwargs.copy().update({'src': src_out, 'tgt': tgt_out})
        
        return results 

class SpmMultilingualTextProcessor(TextProcessor):
    """First BPE, then add multilingual tag."""
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.bper = SpmTextProcessor(src_lang, tgt_lang, **kwargs)
        self.mult = MultilingualTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.bper.preprocess(text).strip()
        text = self.mult.preprocess(text).strip()
        return text 

    def postprocess(self, text):
        return self.bper.postprocess(text)

    def preprocess_file(self, input_fp, output_fp):
        fp = self.bper.preprocess_file(input_fp, input_fp + '.bpe')
        fp = self.mult.preprocess_file(fp, output_fp)
        return output_fp

    def postprocess_file(self, input_fp, output_fp):
        return self.bper.postprocess_file(input_fp, output_fp)

    def preprocess_before_wrap(self, text):
        return self.bper.preprocess(text).strip()

    def preprocess_after_wrap(self, text):
        new_text = ''
        for line in text.split(os.linesep):
            line = self.mult.preprocess(line).strip()
            new_text += line + os.linesep
        return new_text 

    def preprocess_before_wrap_file(self, input_fp, output_fp):
        return self.bper.preprocess_file(input_fp, output_fp)
    
    def preprocess_after_wrap_file(self, input_fp, output_fp):
        with open(input_fp, 'r', encoding='utf-8') as infile, \
             open(output_fp, 'w', encoding='utf-8') as outfile:
            for line in infile:
                line = self.preprocess_after_wrap(line)
                outfile.write(line)
        return outfile 

    def prepare_training_data(self, output_dir: str, src: str, tgt: str, **kwargs) -> list:
        r"""
        Prepare training data by preprocessing it with this text processor. 
        We must return output with {'src': src_file, 'tgt': tgt_file, ...} 
        See edinmt.cli.prepare_training_data
        """
        os.makedirs(output_dir, exist_ok=True)

        src_out = os.path.join(output_dir, os.path.basename(src)) + self.ext
        src_out = self.preprocess_file(src, src_out)
        tgt_out = os.path.join(output_dir, os.path.basename(tgt)) + self.ext
        tgt_out = self.bper.preprocess_file(tgt, tgt_out)
        results = kwargs.copy().update({'src': src_out, 'tgt': tgt_out})
        
        return results 

class MosesTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.moses_tok = MosesTokenizerTextProcessor(src_lang, tgt_lang, **kwargs)
        self.moses_trc = MosesTruecaserTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.moses_tok.preprocess(text).strip()
        text = self.moses_trc.preprocess(text).strip()
        return text 

    def postprocess(self, text):
        text = self.moses_trc.postprocess(text).strip()
        text = self.moses_tok.postprocess(text).strip()
        return text

    def preprocess_file(self, input_fp, output_fp):
        fp = self.moses_tok.preprocess_file(input_fp, input_fp + '.tok')
        fp = self.moses_trc.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.moses_trc.postprocess_file(fp, input_fp + '.detc')
        fp = self.moses_tok.postprocess_file(fp, output_fp)
        return fp

class MosesSubwordNmtTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.moses = MosesTextProcessor(src_lang, tgt_lang, **kwargs)
        self.sbwrd = SubwordNmtTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.moses.preprocess(text).strip()
        text = self.sbwrd.preprocess(text).strip()
        return text 

    def postprocess(self, text):
        text = self.sbwrd.postprocess(text).strip()
        text = self.moses.postprocess(text).strip()
        return text

    def preprocess_file(self, input_fp, output_fp):
        fp = self.moses.preprocess_file(input_fp, input_fp + '.moses')
        fp = self.sbwrd.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.sbwrd.postprocess_file(input_fp, input_fp + '.debpe')
        fp = self.moses.postprocess_file(fp, output_fp)
        return fp

class NormSubwordNmtTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.norm = NormTextProcessor(src_lang, tgt_lang, **kwargs) 
        self.sbwrd = SubwordNmtTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        return self.sbwrd.preprocess(self.norm.preprocess(text))

    def postprocess(self, text):
        return self.norm.postprocess(self.sbwrd.postprocess(text))

class QueryMosesSubwordNmtTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.moses = MosesTextProcessor(src_lang, tgt_lang, **kwargs)
        self.query = QueryAppendedTextProcessor(src_lang, tgt_lang, **kwargs)
        self.sbwrd = SubwordNmtTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.query.preprocess(text)
        text = self.moses.preprocess(text)
        text = self.sbwrd.preprocess(text)
        return text 

    def postprocess(self, text):
        text = self.sbwrd.postprocess(text)
        text = self.moses.postprocess(text)
        return text 

    def preprocess_file(self, input_fp, output_fp):
        fp = self.query.preprocess_file(input_fp, input_fp + '.query')
        fp = self.moses.preprocess_file(fp, fp + '.moses')
        fp = self.sbwrd.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.sbwrd.postprocess_file(input_fp, input_fp + '.debpe')
        fp = self.moses.postprocess_file(fp, output_fp)
        return fp

class RemovePunctMosesSubwordNmtTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.punct = RemovePunctTextProcessor(src_lang, tgt_lang, **kwargs)
        self.moses = MosesTextProcessor(src_lang, tgt_lang, **kwargs)
        self.sbwrd = SubwordNmtTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.punct.preprocess(text)
        text = self.moses.preprocess(text)
        text = self.sbwrd.preprocess(text)
        return text 

    def postprocess(self, text):
        text = self.sbwrd.postprocess(text)
        text = self.moses.postprocess(text)
        return text 

    def preprocess_file(self, input_fp, output_fp):
        fp = self.punct.preprocess_file(input_fp, input_fp + '.punct')
        fp = self.moses.preprocess_file(fp, fp + '.moses')
        fp = self.sbwrd.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.sbwrd.postprocess_file(input_fp, input_fp + '.debpe')
        fp = self.moses.postprocess_file(fp, output_fp)
        return fp

class MosesNormPunctMosesSubwordNmtTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.punct = MosesNormPunctTextProcessor(src_lang, tgt_lang, **kwargs)
        self.moses = MosesTextProcessor(src_lang, tgt_lang, **kwargs)
        self.sbwrd = SubwordNmtTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.punct.preprocess(text)
        text = self.moses.preprocess(text)
        text = self.sbwrd.preprocess(text)
        return text 

    def postprocess(self, text):
        text = self.sbwrd.postprocess(text)
        text = self.moses.postprocess(text)
        return text 

    def preprocess_file(self, input_fp, output_fp):
        fp = self.punct.preprocess_file(input_fp, input_fp + '.punct')
        fp = self.moses.preprocess_file(fp, fp + '.moses')
        fp = self.sbwrd.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.sbwrd.postprocess_file(input_fp, input_fp + '.debpe')
        fp = self.moses.postprocess_file(fp, output_fp)
        return fp

class QuerySpmTextProcessor(TextProcessor):
    def __init__(self, src_lang, tgt_lang, **kwargs):
        super().__init__(src_lang, tgt_lang, **kwargs)
        self.query = QueryAppendedTextProcessor(src_lang, tgt_lang, **kwargs)
        self.sbwrd = SpmTextProcessor(src_lang, tgt_lang, **kwargs)

    def preprocess(self, text):
        text = self.query.preprocess(text)
        text = self.sbwrd.preprocess(text)
        return text 

    def postprocess(self, text):
        text = self.sbwrd.postprocess(text)
        return text 

    def preprocess_file(self, input_fp, output_fp):
        fp = self.query.preprocess_file(input_fp, input_fp + '.query')
        fp = self.sbwrd.preprocess_file(fp, output_fp)
        return fp
    
    def postprocess_file(self, input_fp, output_fp):
        fp = self.sbwrd.postprocess_file(input_fp, output_fp)
        return fp
