import logging
import re
import subprocess
from abc import ABC, abstractmethod

from edinmt import CONFIG 
from edinmt.configs.config import all_members

#be explicit, so that logging occurs even if this is run as main
logger = logging.getLogger('edinmt.scorers.scorers')
logger.setLevel(CONFIG.LOG_LEVEL)


class Scorer(ABC):
    def __init__(self, **kwargs):
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

    @abstractmethod
    def score_file(self, pred_fp, ref_fp):
        raise NotImplementedError

class SacrebleuScorer(Scorer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def score_file(self, pred_fp, ref_fp):
        if isinstance(ref_fp, list):
            ref_fp = ' '.join(ref_fp)
        cmd = f'cat {pred_fp} | sacrebleu {ref_fp}'
        logger.debug('RUNNING: ' + cmd)
        result = subprocess.check_output(cmd, shell=True)
        result = result.decode()
        logger.debug(f"SACREBLEU RESULT: {result}")
        bleu = result.split(" = ")[1].split(" ")[0]
        return bleu 

class QueryScorer(Scorer):
    def __init__(self, query_fp=None, **kwargs):
        super().__init__(**kwargs)
        self.query_fp = query_fp

    @staticmethod
    def calculate(pred_fp, query_fp):
        inserted = 0
        expected = 0
        sentences_w_expected_terms = 0
        total_metric = 0
        with open(pred_fp, 'r', encoding='utf-8') as pred_fh, \
             open(query_fp, 'r', encoding='utf-8') as query_fh:
            for line in pred_fh:
                    target = line.strip()
                    terms = query_fh.readline().strip()
                    if not terms:
                        continue
                    terms = terms.split('|||')
                    sentences_w_expected_terms += 1

                    #count this sentence's total
                    expected_terms = len(terms)
                    inserted_terms = sum([target.count(term.strip()) for term in terms])

                    metric = abs(inserted_terms - expected_terms) / expected_terms
                    total_metric += 1 - metric
                    inserted += inserted_terms
                    expected += expected_terms

        if not sentences_w_expected_terms:
            final_metric = None
        else:
            final_metric = total_metric / sentences_w_expected_terms
        return inserted, expected, final_metric 

    def score_file(self, pred_fp, ref_fp):
        result = QueryScorer.calculate(pred_fp, self.query_fp)
        return {'inserted': result[0], 'expected': result[1], 'score': result[2]} 

