import json
import logging
import os
import pathlib
import shutil
import unittest
from unittest import mock

from edinmt.configs.config import TestConfig
from edinmt.cli import translate_folder, translate_input

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_cli')
logger.setLevel(TestConfig.LOG_LEVEL)

#this file is 13176 bytes long, 100 lines long
TEST_FILE = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "original", "chunk.fa")
PLAYGROUND_DIR = os.path.join(TestConfig.ROOT_DIR, "edinmt", "tests", "data", "playground")

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
        os.makedirs(self.mtout_dir, exist_ok=True)
        os.makedirs(self.translate_me_dir, exist_ok=True)
        os.makedirs(os.path.join(self.translate_me_dir, 'subfolder'), exist_ok=True)
        for i in range(3):
            shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, f'txt.{i}'))
        shutil.copy(TEST_FILE, os.path.join(self.translate_me_dir, os.path.join('subfolder', f'txt.3')))

    def tearDown(self):
        r"""
        Completely delete the entire contents of the testing directory 
        that we created in setUp.
        """
        if TestConfig.PURGE:
            shutil.rmtree(self.translate_me_dir)
            shutil.rmtree(self.mtout_dir)

    def test_cli_translate_folder_fast_1best_fmt_json(self):
        translate_folder.main(
            src_lang='fa',
            tgt_lang='en',
            input_dir=self.translate_me_dir, 
            output_dir=self.mtout_dir,
            system_name='faen',
            use_mode='fast',
            n_best=False,
            n_best_words=False,
            fmt='json',
        )

        result = set([os.path.join(dp, f) for dp, dn, fn in os.walk(self.mtout_dir) for f in fn])
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
                self.assertTrue('|||' not in data[0])

        self.assertEqual(answer, result)


    def test_cli_translate_folder_fast_1best_fmt_marian(self):
        translate_folder.main(
            src_lang='fa',
            tgt_lang='en',
            input_dir=self.translate_me_dir, 
            output_dir=self.mtout_dir,
            use_mode='fast',
            system_name='faen',
            n_best=False,
            n_best_words=False,
            fmt='marian',
        )

        result = set([os.path.join(dp, f) for dp, dn, fn in os.walk(self.mtout_dir) for f in fn])
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
                self.assertEqual(data[0].split(' ||| ')[0], '0')
                self.assertEqual(data[99].split(' ||| ')[0], '99')

        self.assertEqual(answer, result)

    def test_cli_translate_folder_fast_1best_fmt_text(self):
        translate_folder.main(
            src_lang='fa',
            tgt_lang='en',
            input_dir=self.translate_me_dir, 
            output_dir=self.mtout_dir,
            use_mode='fast',
            system_name='faen',
            n_best=False,
            n_best_words=False,
            fmt='text',
        )

        result = set([os.path.join(dp, f) for dp, dn, fn in os.walk(self.mtout_dir) for f in fn])
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





if __name__ == '__main__':
    unittest.main()