import io
import json
import logging
import unittest
from collections import namedtuple

from edinmt.configs.config import TestConfig
from edinmt import translate_input
from edinmt.get_settings import get_decoder_settings 

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_langs')
logger.setLevel(TestConfig.LOG_LEVEL)

#This is where we can add more language direction tests
LangTest = namedtuple('LangTest', ['system', 'src_lang', 'tgt_lang', 'src_txt', 'tgt_txt'])
lang_tests = [
    LangTest('kaen', 'ka', 'en', 
        'ნს, რამ თდპსქკთ.',
        'My daughter is dead.'
    ),
    LangTest('enka', 'en', 'ka', 
        'My daughter is dead.',
        'ნს, რამ თდპსქკთ.'
    ),
    LangTest('kaen_query', 'ka', 'en', 
        'ნს, რამ თდპსქკთ. ||| daughter',
        'My daughter is dead.'
    ),
    LangTest('kken_query', 'kk', 'en', 
        'Ақша-несие саясатының сценарийін қайта жазсақ ||| policy\n'\
        'Бірақ бұл тұжырымды жоққа шығаратын себептер жеткілікті ||| the reasons.',
        "Performance of monetary policy\n"\
        "But the reasons that dissolve this concept are sufficient."
    ),
    LangTest('kken', 'kk', 'en', 
        'Ақша-несие саясатының сценарийін қайта жазсақ\n'\
        'Бірақ бұл тұжырымды жоққа шығаратын себептер жеткілікті.',
        "Performance of monetary policy\n"\
        "But the reasons that dissolve this concept are sufficient."
    ),
    LangTest('enkk', 'en', 'kk', 
        "Performance of monetary policy\n"\
        "But the reasons that dissolve this concept are sufficient.",
        'Ақша-несие саясатының сценарийін қайта жазсақ\n'\
        'Бірақ бұл тұжырымды жоққа шығаратын себептер жеткілікті.'

    ),
    LangTest('kkenru', 'kk', 'en', 
        'Ақша-несие саясатының сценарийін қайта жазсақ\n'\
        'Бірақ бұл тұжырымды жоққа шығаратын себептер жеткілікті.',
        "Performance of monetary policy\n"\
        "But the reasons that dissolve this concept are sufficient."
    ),
    LangTest('kkenru', 'en', 'kk', 
        "Performance of monetary policy\n"\
        "But the reasons that dissolve this concept are sufficient.",
        'Ақша-несие саясатының сценарийін қайта жазсақ\n'\
        'Бірақ бұл тұжырымды жоққа шығаратын себептер жеткілікті.'

    ),
    LangTest('faen', 'fa', 'en', 
        'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.\n'\
        'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.',
        "In Berkeley, we call these robots Exoskeleton.\n"
        "In Berkeley, we call these robots Exoskeleton."
    ),
    LangTest('enfa', 'en', 'fa', 
        "In Berkeley, we call these robots Exoskeleton.\n"
        "In Berkeley, we call these robots Exoskeleton.",
        'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.\n'\
        'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.',
    ),
    LangTest('bgen', 'bg', 'en',
        'iтова е тест.',
        'This is a test.',
    ),
    LangTest('enbg', 'en', 'bg',
        'This is a test.',
        'iтова е тест.',
    ),
    LangTest('lten', 'lt', 'en',
        'Čia testas.',
        'This is a test',
    ),
    LangTest('enlt', 'en', 'lt',
        'This is a test',
        'Čia testas.',
    ),
    LangTest('soen', 'so', 'en',
        'Tani waa tijaabo.',
        'This is a test',
    ),
    LangTest('enso', 'en', 'so',
        'This is a test',
        'Tani waa tijaabo.',
    ),
    LangTest('swen', 'sw', 'en',
        'Huu ni mtihani.',
        'This is a test',
    ),
    LangTest('ensw', 'en', 'sw',
        'This is a test',
        'Huu ni mtihani.',
    ),
    LangTest('tlen', 'tl', 'en',
        'Ito ay isang pagsubok.',
        'This is a test',
    ),
    LangTest('entl', 'en', 'tl',
        'This is a test',
        'Ito ay isang pagsubok.',
    ),
    LangTest('psen', 'ps', 'en',
        'ﺩﺍ ﺍﺰﻣﻭیﻦﻫ ﺪﻫ.',
        'This is a test',
    ),
    LangTest('enps', 'en', 'ps',
        'This is a test',
        'ﺩﺍ ﺍﺰﻣﻭیﻦﻫ ﺪﻫ.',
    ),
]

def translation_test(lang_test, user_settings):
    decoder_settings = get_decoder_settings(
        lang_test.src_lang, lang_test.tgt_lang, 
        config=TestConfig, user_settings=user_settings)

    input_fh = io.StringIO(lang_test.src_txt) 
    output_fh = io.StringIO()

    returncode = translate_input.translate(
        subcommand=decoder_settings.cmd,
        input_fh=input_fh,
        output_fh=output_fh,
        text_processor=decoder_settings.text_processor, 
        n_best=decoder_settings.n_best,
        n_best_words=decoder_settings.n_best_words,
        fmt=decoder_settings.fmt
    )

    output_fh.seek(0)
    mtout = output_fh.read()
    data = mtout.split('\n')

    try:
        assert returncode == 0
        #add 1 because of final \n at end of mt output
        assert len(data) == len(lang_test.tgt_txt.split('\n'))+1
        assert json.loads(data[0])['id'] == 0
        assert '|||' not in data[0]
    except AssertionError:
        return False, mtout, decoder_settings.cmd
    else:
        return True, mtout, decoder_settings.cmd


class TestSystems(unittest.TestCase):

    def test_langs(self):
        results = {True: [], False: []}

        for lang_test in lang_tests:
            user_settings = dict(
                MODE='fast', 
                NBEST_WORDS=False,
                NBEST=False,
                FMT='json',
                CPU_COUNT=1, #we test 1 line at a time, so just load model quickly
                SYSTEM=lang_test.system,
            )
            success, mtout, cmd = translation_test(lang_test, user_settings)
            results[success].append( (lang_test, mtout, cmd) )

        #print outputs so we can make sure it looks correct
        for lang_test, mtout, cmd in results[True]:
            msg = f"SUCCESS: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)
        #print the failures second so they're more salient
        for lang_test, mtout, cmd in results[False]: 
            msg = f"***FAIL***: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)
        
        if results[False]:
            logger.info(f'FAILED test_langs: {[item[0].system for item in results[False]]}')
            
        #assert we have no failures 
        self.assertFalse(results[False])

    def test_langs_no_system(self):
        results = {True: [], False: []}

        for lang_test in lang_tests:
            user_settings = dict(
                MODE='fast', 
                NBEST_WORDS=False,
                NBEST=False,
                FMT='json',
                CPU_COUNT=1, #we test 1 line at a time, so just load model quickly
                SYSTEM=None
            )
            success, mtout, cmd = translation_test(lang_test, user_settings)
            results[success].append( (lang_test, mtout, cmd) )

        #print outputs so we can make sure it looks correct
        for lang_test, mtout, cmd in results[True]:
            msg = f"SUCCESS: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)
        #print the failures second so they're more salient
        for lang_test, mtout, cmd in results[False]: 
            msg = f"***FAIL***: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)

        if results[False]:
            logger.info(f'FAILED test_langs_no_system: {[item[0].system for item in results[False]]}')

        #assert we have no failures 
        self.assertFalse(results[False])

    def test_langs_type_audio(self):
        results = {True: [], False: []}

        for lang_test in lang_tests:
            user_settings = dict(
                MODE='fast', 
                NBEST_WORDS=False,
                NBEST=False,
                FMT='json',
                CPU_COUNT=1, #we test 1 line at a time, so just load model quickly
                SYSTEM=None,
                TYPE='audio'
            )
            success, mtout, cmd = translation_test(lang_test, user_settings)
            results[success].append( (lang_test, mtout, cmd) )

        #print outputs so we can make sure it looks correct
        for lang_test, mtout, cmd in results[True]:
            msg = f"SUCCESS: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)
        #print the failures second so they're more salient
        for lang_test, mtout, cmd in results[False]: 
            msg = f"***FAIL***: {lang_test.system} "\
                  f"{lang_test.src_lang}2{lang_test.tgt_lang}: "\
                  f"{' '.join(cmd)}\n"\
                  f"SRC:\n{lang_test.src_txt}\n"\
                  f"REF:\n{lang_test.tgt_txt}\n"\
                  f"OUT:\n{mtout}\n"
            logger.info(msg)
        
        if results[False]:
            logger.info(f'FAILED test_langs_type_audio: {[item[0].system for item in results[False]]}')

        #assert we have no failures 
        self.assertFalse(results[False])



if __name__ == '__main__':
    unittest.main()