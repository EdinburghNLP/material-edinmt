import json
import logging
import os
import pathlib
import shutil
import unittest
from unittest import mock

from edinmt import translate_folder
from edinmt.configs.config import TestConfig
from edinmt.get_settings import get_decoder_settings 

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_translate')
logger.setLevel(TestConfig.LOG_LEVEL)

#this file is 13176 bytes long, 100 lines long
TEST_FILE = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "original", "chunk.fa")
PLAYGROUND_DIR = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "playground")

@unittest.skip('for now')
class TestTranslateFolder(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        r"""
        Make a fake directory structure for testing purposes, which will be
        deleted at the end of the test.
        """
        self.name = self.id().split('.')[-1]
        self.translate_me_dir = os.path.join(PLAYGROUND_DIR, self.name, 'translate_me')
        self.mtout_dir = os.path.join(PLAYGROUND_DIR, self.name, 'mtout')
        os.makedirs(self.translate_me_dir, exist_ok=True)
        os.makedirs(os.path.join(self.translate_me_dir, 'subfolder'), exist_ok=True)
        for i in range(3):
            shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, f'txt.{i}'))
        shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, os.path.join('subfolder', f'txt.3')))
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

    def test_translate_folder_1best_fmt_json(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'json'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if 'tmp' not in r])
        answer = set([
            f'{self.mtout_dir}/txt.0', 
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), 100)
                self.assertTrue(json.loads(data[0]))
                self.assertEqual(json.loads(data[0])['id'], 0)
                self.assertEqual(json.loads(data[99])['id'], 99)
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)

    def test_translate_folder_nbest_fmt_json(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = True
        user_settings['FMT'] = 'json'

        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")
        
        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if r != 'tmp'])
        answer = set([
            f'{self.mtout_dir}/txt.0',
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        total = decoder_settings.n_best*100

        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), total)
                self.assertEqual(json.loads(data[0])['id'], 0)
                self.assertEqual(json.loads(data[total-1])['id'], 99)
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)

    def test_translate_folder_1best_fmt_marian(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'marian'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if 'tmp' not in r])
        answer = set([
            f'{self.mtout_dir}/txt.0', 
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), 100)
                self.assertRaises(json.JSONDecodeError, json.loads, s=data[0])
                self.assertEqual(data[0].split(' ||| ')[0], '0')
                self.assertEqual(data[99].split(' ||| ')[0], '99')

        self.assertEqual(answer, result)

    def test_translate_folder_1best_fmt_text(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'text'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if 'tmp' not in r])
        answer = set([
            f'{self.mtout_dir}/txt.0', 
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), 100)
                self.assertRaises(json.JSONDecodeError, json.loads, s=data[0])
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)


class TestTranslateFolderNbestWords(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        r"""
        Make a fake directory structure for testing purposes, which will be
        deleted at the end of the test.
        """
        self.name = self.id().split('.')[-1]
        self.translate_me_dir = os.path.join(PLAYGROUND_DIR, self.name, 'translate_me')
        self.mtout_dir = os.path.join(PLAYGROUND_DIR, self.name, 'mtout')
        os.makedirs(self.translate_me_dir, exist_ok=True)
        os.makedirs(os.path.join(self.translate_me_dir, 'subfolder'), exist_ok=True)
        for i in range(3):
            shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, f'txt.{i}'))
        shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, os.path.join('subfolder', f'txt.3')))
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
            shutil.rmtree(self.translate_me_dir)
            shutil.rmtree(self.mtout_dir)

    def test_translate_folder_1best_json_nbest_words(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = False
        user_settings['FMT'] = 'json'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt,
            purge=TestConfig.PURGE,
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if 'tmp' not in r])
        answer = set([
            f'{self.mtout_dir}/txt.0', 
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), 100)
                self.assertEqual(json.loads(data[0])['id'], 0)
                self.assertEqual(json.loads(data[99])['id'], 99)
                self.assertTrue(json.loads(data[0])['nbest_words'])
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)

    def test_translate_folder_nbest_json_nbest_words(self):
        user_settings = self.user_settings.copy()
        user_settings['NBEST'] = True
        user_settings['FMT'] = 'json'
        
        decoder_settings = get_decoder_settings(
            'fa', 'en', config=TestConfig, user_settings=user_settings)

        logger.debug(f"{self.name}: {decoder_settings}")

        returncode = translate_folder.translate(
            subcommand=decoder_settings.cmd,
            input_dir=self.translate_me_dir,
            output_dir=self.mtout_dir,
            text_processor=decoder_settings.text_processor, 
            n_best=decoder_settings.n_best, 
            n_best_words=decoder_settings.n_best_words,
            fmt=decoder_settings.fmt,
            purge=TestConfig.PURGE,
        )

        result = set([os.path.join(r, f) 
                        for r, d, fs in os.walk(self.mtout_dir) 
                            for f in fs 
                                if 'tmp' not in r])
        answer = set([
            f'{self.mtout_dir}/txt.0', 
            f'{self.mtout_dir}/txt.1', 
            f'{self.mtout_dir}/txt.2', 
            f'{self.mtout_dir}/subfolder/txt.3', 
        ])

        total = decoder_settings.n_best*100
        
        for name in ['txt.0', 'txt.1', 'txt.2', os.path.join('subfolder', 'txt.3')]:
            with open(os.path.join(self.mtout_dir, name), 'r', encoding='utf-8') as fh:
                data = fh.readlines()
                self.assertEqual(len(data), total)
                self.assertEqual(json.loads(data[0])['id'], 0)
                self.assertEqual(json.loads(data[total-1])['id'], 99)
                self.assertTrue(json.loads(data[0])['nbest_words'])
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)


if __name__ == '__main__':
    unittest.main()