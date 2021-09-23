import json
import logging
import os
import pathlib
import shutil
import unittest
from unittest import mock

from edinmt.configs.config import TestConfig
from edinmt import translate_input 
from edinmt.get_settings import get_decoder_settings 

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_translate')
logger.setLevel(TestConfig.LOG_LEVEL)

#this file is 13176 bytes long, 100 lines long
TEST_FILE = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "original", "chunk.fa")
PLAYGROUND_DIR = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "playground")

class TestTranslateInput(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        r"""
        Make a fake directory structure for testing purposes, which will be
        deleted at the end of the test.
        """
        self.name = self.id().split('.')[-1]
        self.mtout_dir = os.path.join(PLAYGROUND_DIR, self.name, 'mtout')
        os.makedirs(self.mtout_dir, exist_ok=True)
        self.user_settings = dict(
            MODE='fast', 
            NBEST_WORDS=False,
            SYSTEM='faen'
        )

    def tearDown(self):
        r"""
        Completely delete the entire contents of the testing directory 
        that we created in setUp.
        """
        if TestConfig.PURGE:
            shutil.rmtree(self.translate_me_dir)
            shutil.rmtree(self.mtout_dir)

    def test_translate_input_nbest_fmt_json(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = True
        user_settings['FMT'] = 'json'

        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        input_fh = TEST_FILE
        output_fh = os.path.join(self.mtout_dir, 'nbest_json.txt')

        with open(input_fh, 'r', encoding='utf-8') as infile, \
             open(output_fh, 'w', encoding='utf-8') as outfile:
            returncode = translate_input.translate(
                subcommand=decoder_settings.cmd,
                input_fh=infile,
                output_fh=outfile,
                text_processor=decoder_settings.text_processor, 
                n_best=decoder_settings.n_best,
                n_best_words=decoder_settings.n_best_words,
                fmt=decoder_settings.fmt
            )

        with open(output_fh, 'r', encoding='utf-8') as infile:
            data = infile.readlines()

        total = decoder_settings.n_best*100
        
        self.assertEqual(returncode, 0)
        self.assertEqual(len(data), total)
        self.assertEqual(json.loads(data[0])['id'], 0)
        self.assertEqual(json.loads(data[total-1])['id'], 99)
        self.assertTrue('|||' not in data[0])

    def test_translate_input_nbest_fmt_marian(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = True
        user_settings['FMT'] = 'marian'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        input_fh = TEST_FILE
        output_fh = os.path.join(self.mtout_dir, 'nbest_plaintext.txt')

        with open(input_fh, 'r', encoding='utf-8') as infile, \
             open(output_fh, 'w', encoding='utf-8') as outfile:
            returncode = translate_input.translate(
                subcommand=decoder_settings.cmd,
                input_fh=infile,
                output_fh=outfile,
                text_processor=decoder_settings.text_processor, 
                n_best=decoder_settings.n_best,
                n_best_words=decoder_settings.n_best_words,
                fmt=decoder_settings.fmt
            )

        with open(output_fh, 'r', encoding='utf-8') as infile:
            data = infile.readlines()

        total = decoder_settings.n_best*100
        self.assertEqual(returncode, 0)
        self.assertEqual(len(data), total)
        self.assertEqual(data[0].split(' ||| ')[0], '0')
        self.assertEqual(data[total-1].split(' ||| ')[0], '99')

    def test_translate_input_1best_fmt_json(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'json'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)
            
        logger.debug(f"{self.name}: {decoder_settings}")

        input_fh = TEST_FILE
        output_fh = os.path.join(self.mtout_dir, '1best_json.txt')

        with open(input_fh, 'r', encoding='utf-8') as infile, \
             open(output_fh, 'w', encoding='utf-8') as outfile:
            returncode = translate_input.translate(
                subcommand=decoder_settings.cmd,
                input_fh=infile,
                output_fh=outfile,
                text_processor=decoder_settings.text_processor, 
                n_best=decoder_settings.n_best,
                n_best_words=decoder_settings.n_best_words,
                fmt=decoder_settings.fmt,
            )

        with open(output_fh, 'r', encoding='utf-8') as infile:
            data = infile.readlines()
        
        self.assertEqual(returncode, 0)
        self.assertEqual(len(data), 100)
        self.assertEqual(json.loads(data[0])['id'], 0)
        self.assertEqual(json.loads(data[99])['id'], 99)
        self.assertTrue('|||' not in data[0])

    def test_translate_input_1best_fmt_marian(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'marian'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        input_fh = TEST_FILE
        output_fh = os.path.join(self.mtout_dir, '1best_plaintext.txt')

        with open(input_fh, 'r', encoding='utf-8') as infile, \
             open(output_fh, 'w', encoding='utf-8') as outfile:
            returncode = translate_input.translate(
                subcommand=decoder_settings.cmd,
                input_fh=infile,
                output_fh=outfile,
                text_processor=decoder_settings.text_processor, 
                n_best=decoder_settings.n_best,
                n_best_words=decoder_settings.n_best_words,
                fmt=decoder_settings.fmt,
            )

        with open(output_fh, 'r', encoding='utf-8') as infile:
            data = infile.readlines()
        
        self.assertEqual(returncode, 0)
        self.assertEqual(len(data), 100)
        self.assertEqual(data[0].split(' ||| ')[0], '0')
        self.assertEqual(data[99].split(' ||| ')[0], '99')


class TestTranslateInputNbestWords(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        r"""
        Make a fake directory structure for testing purposes, which will be
        deleted at the end of the test.
        """
        self.name = self.id().split('.')[-1]
        self.mtout_dir = os.path.join(PLAYGROUND_DIR, self.name, 'mtout')
        os.makedirs(self.mtout_dir, exist_ok=True)
        self.user_settings = dict(
            MODE='fast', 
            NBEST_WORDS=True,
            SYSTEM='faen'
        )

    def tearDown(self):
        r"""
        Completely delete the entire contents of the testing directory 
        that we created in setUp.
        """
        if TestConfig.PURGE:
            shutil.rmtree(self.mtout_dir)

    def test_translate_input_1best_json_nbest_words(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'json'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        input_fh = TEST_FILE
        output_fh = os.path.join(self.mtout_dir, '1best_json_nbest_words.txt')

        with open(input_fh, 'r', encoding='utf-8') as infile, \
             open(output_fh, 'w', encoding='utf-8') as outfile:
            returncode = translate_input.translate(
                subcommand=decoder_settings.cmd,
                input_fh=infile,
                output_fh=outfile,
                text_processor=decoder_settings.text_processor, 
                n_best=decoder_settings.n_best,
                n_best_words=decoder_settings.n_best_words,
                fmt=decoder_settings.fmt,
            )

        with open(output_fh, 'r', encoding='utf-8') as infile:
            data = infile.readlines()
        
        self.assertEqual(returncode, 0)
        self.assertEqual(len(data), 100)
        self.assertEqual(json.loads(data[0])['id'], 0)
        self.assertEqual(json.loads(data[99])['id'], 99)
        self.assertTrue(json.loads(data[0])['nbest_words'])
        self.assertTrue('|||' not in data[0])


if __name__ == '__main__':
    unittest.main()