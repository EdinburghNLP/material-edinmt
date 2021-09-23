#!/usr/bin/python3.7
#-*- coding: UTF-8 -*-
import json
import logging
import unittest

import websocket

from edinmt.configs.config import TestConfig

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_servers')
logger.setLevel(TestConfig.LOG_LEVEL)

class TestRunningTranslateServer(unittest.TestCase):
    r"""
    This is more like an integration test. The Docker environment sets
    everything up (see the README.md for how to do this correctly), but
    if you are running these tests outside the Docker environment, you
    will first need to:

    1) export environment variables in your shell to prepare correct settings;
       see config/configs/config.py for all options and 
    2) python3.7 edinmt/launch/launch_marian_server.py
    3) python3.7 edinmt/launch/launch_pipeline_server.py
    """
    def setUp(self):
        host = 'localhost'
        port = 8081
        ws = None
        try:
            self.ws = websocket.create_connection("ws://%s:%s/" %(host, port))
        except:
            raise unittest.SkipTest("Skipping due to unavailable websocket marian and pipeline servers.")

    def tearDown(self):
        if self.ws:
            self.ws.close()

    def test_fa(self):
        all_input = {'src_lang': 'fa', 'tgt_lang': 'en', 'text': 'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_kk(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_kk_query(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'query': 'query', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_multiline(self):
        all_input = {
            'src_lang': 'fa', 
            'tgt_lang': 'en', 
            'text': 'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.\nما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.'
        }
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_long_line(self):
        all_input = {
            'src_lang': 'kk', 'tgt_lang': 'en', 'text': "түсіндірме сөздік” → ]]> https://blog.daniyar.info/2019/02/%d0%bd%d2%b1%d1%80%d1%82%d0%b0%d1%81-%d0%be%d2%a3%d0%b4%d0%b0%d1%81%d1%8b%d0%bd%d0%be%d0%b2-%d0%b0%d1%80%d0%b0%d0%b1%d1%88%d0%b0-%d2%9b%d0%b0%d0%b7%d0%b0%d2%9b%d1%88%d0%b0-%d1%82%d2%af%d1%81%d1%96/feed/ 0 3295 Қос тілдік саясатының баяғы жартасы https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/ https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/#respond Wed, 22 Feb 2017 20:31:43 +0000 https://blog.daniyar.info/?p=2456 Continue reading Қос тілдік саясатының баяғы жартасы → ]]> https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/feed/ 0 2456 Өліспей беріспейтін орысшыл аудармашылар https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/ https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/#respond Sun, 22 Apr 2012 16:51:35 +0000 https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/"
        }
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_long_line_query(self):
        all_input = {
            'src_lang': 'kk', 'tgt_lang': 'en', 'query': 'dictionary', 'text': "түсіндірме сөздік” → ]]> https://blog.daniyar.info/2019/02/%d0%bd%d2%b1%d1%80%d1%82%d0%b0%d1%81-%d0%be%d2%a3%d0%b4%d0%b0%d1%81%d1%8b%d0%bd%d0%be%d0%b2-%d0%b0%d1%80%d0%b0%d0%b1%d1%88%d0%b0-%d2%9b%d0%b0%d0%b7%d0%b0%d2%9b%d1%88%d0%b0-%d1%82%d2%af%d1%81%d1%96/feed/ 0 3295 Қос тілдік саясатының баяғы жартасы https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/ https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/#respond Wed, 22 Feb 2017 20:31:43 +0000 https://blog.daniyar.info/?p=2456 Continue reading Қос тілдік саясатының баяғы жартасы → ]]> https://blog.daniyar.info/2017/02/%d2%9b%d0%be%d1%81-%d1%82%d1%96%d0%bb%d0%b4%d1%96%d0%ba-%d1%81%d0%b0%d1%8f%d1%81%d0%b0%d1%82%d1%8b%d0%bd%d1%8b%d2%a3-%d0%b1%d0%b0%d1%8f%d2%93%d1%8b-%d0%b6%d0%b0%d1%80%d1%82%d0%b0%d1%81%d1%8b/feed/ 0 2456 Өліспей беріспейтін орысшыл аудармашылар https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/ https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/#respond Sun, 22 Apr 2012 16:51:35 +0000 https://blog.daniyar.info/2012/04/%d3%a9%d0%bb%d1%96%d1%81%d0%bf%d0%b5%d0%b9-%d0%b1%d0%b5%d1%80%d1%96%d1%81%d0%bf%d0%b5%d0%b9%d1%82%d1%96%d0%bd-%d0%be%d1%80%d1%8b%d1%81%d1%88%d1%8b%d0%bb-%d0%b0%d1%83%d0%b4%d0%b0%d1%80%d0%bc%d0%b0/"
        }
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_two_sents(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ\nАқша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_two_sents_query(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'query': 'query\nquery', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ\nАқша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)

    def test_two_sents_query_malformed(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'query': 'query', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ\nАқша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        logger.info(f'REQUEST: {all_input}')
        self.ws.send(all_input)
        result = self.ws.recv()
        logger.info(f'RESPONSE: {result}')
        self.assertTrue(result)
        self.assertTrue('error' in result)

    def test_many_requests(self):
        all_input = {'src_lang': 'kk', 'tgt_lang': 'en', 'text': 'Ақша-несие саясатының сценарийін қайта жазсақ'}
        all_input = json.dumps(all_input, ensure_ascii=False)
        results = []
        logger.info(f'REQUEST x500: {all_input}')
        for i in range(500):
            self.ws.send(all_input)
            result = self.ws.recv()
            results.append(result)
        logger.info(f"RESPONSE x{len(results)}")
        self.assertEqual(len(results), 500)




if __name__ == '__main__':
    unittest.main()