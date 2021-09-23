import io
import json
import logging
import unittest

from edinmt.configs.config import TestConfig
from edinmt import parse_marian 

#be explicit so logging occurs correctly even if this is run as main
logger = logging.getLogger('edinmt.tests.test_parse_marian')
logger.setLevel(TestConfig.LOG_LEVEL)


NBEST_WORDS_1BEST_EMPTY = """
</s> |||  the -1.9085 it -3.27291 a -3.66268 there -4.00807 this -4.05654 &quot; -4.37413
"""


#NOTE: These examples have 2 sentences in them, and for pieces, 
#they are always broken into 2 pieces. This is so that we can easily
#compare how different strategies parse the same 2 sentences.

NBEST_WORDS_1BEST = """

sent0 |||  sent1 -2.10365 
top1 |||  top1 -0.942746 
</s> |||  </s> -0.373202 


sent1 |||  sent2 -2.10365 
top1 |||  top1 -0.942746 
</s> |||  </s> -0.373202 

"""

NBEST_WORDS_2BEST = """
0 ||| sent0 top1 ||| F0= -inf ||| -1.69888
sent0 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
</s> |||  </s> -0.373202 

0 ||| sent0 top2 ||| F0= -inf ||| -1.69888
sent0 |||  sent0 -2.10365 
top2 |||  top2 -0.942746 
</s> |||  </s> -0.373202 

1 ||| sent1 top1 ||| F0= -inf ||| -1.69888
sent1 |||  sent1 -2.10365 
top1 |||  top1 -0.942746 
</s> |||  </s> -0.373202 

1 ||| sent1 top2 ||| F0= -inf ||| -1.69888
sent1 |||  sent1 -2.10365 
top2 |||  top2 -0.942746 
</s> |||  </s> -0.373202 

"""

NBEST_WORDS_1BEST_PIECES = """

sent0 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

sent0 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

sent1 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

sent1 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

"""

NBEST_WORDS_2BEST_PIECES = """
0 ||| sent0 top1 piece0 ||| F0= -inf ||| -1.69888
sent0 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

0 ||| sent0 top2 piece0 ||| F0= -inf ||| -1.69888
sent0 |||  second -2.10365 
top2 |||  best -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

1 ||| sent0 top1 piece1 ||| F0= -inf ||| -1.69888
sent0 |||  sent0 -2.10365 
top1 |||  top1 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

1 ||| sent0 top2 piece1 ||| F0= -inf ||| -1.69888
sent0 |||  sent0 -2.10365 
top2 |||  top2 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

2 ||| sent1 top1 piece0 ||| F0= -inf ||| -1.69888
sent1 |||  sent1 -2.10365 
top1 |||  top1 -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

2 ||| sent1 top2 piece0 ||| F0= -inf ||| -1.69888
sent1 |||  second -2.10365 
top2 |||  best -0.942746 
piece0 |||  piece0 -1.73212
</s> |||  </s> -0.373202 

3 ||| sent1 top1 piece1 ||| F0= -inf ||| -1.69888
sent1 |||  sent1 -2.10365 
top1 |||  top1 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

3 ||| sent1 top2 piece1 ||| F0= -inf ||| -1.69888
sent1 |||  sent1 -2.10365 
top2 |||  top2 -0.942746 
piece1 |||  piece1 -1.73212
</s> |||  </s> -0.373202 

"""


class TestParseMarianNbestWords(unittest.TestCase):
    def test_parse_marian_nbestw_1best(self):
        example = io.StringIO(NBEST_WORDS_1BEST)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=1)
        answer = [
            ["sent0 top1"],
            ["sent1 top1"],
        ]
        self.assertEqual([item['translation'] for item in result], answer)
        [self.assertTrue('nbest_words' in item) for item in result]
        self.assertEqual(len(result), 2)

    def test_parse_marian_nbestw_2best(self):
        example = io.StringIO(NBEST_WORDS_2BEST)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=2)
        answer = [
            ["sent0 top1",
            "sent0 top2"],
            ["sent1 top1",
            "sent1 top2"],
        ]
        self.assertEqual([item['translation'] for item in result], answer)
        [self.assertTrue('nbest_words' in item) for item in result]
        self.assertEqual(len(result), 2)

    def test_parse_marian_nbestw_2best_1items(self):
        example = io.StringIO(NBEST_WORDS_2BEST)
        result = parse_marian.parse_nbest_words(example, n_items=1, n_best=2)
        answer = [
            ["sent0 top1",
            "sent0 top2"],
        ]
        self.assertEqual([item['translation'] for item in result], answer)
        [self.assertTrue('nbest_words' in item) for item in result]
        self.assertEqual(len(result), 1)

    def test_unwrap_lines_nbestw_1best_pieces(self):
        example = io.StringIO(NBEST_WORDS_1BEST_PIECES)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=1)
        true_ids = [0, 0, 1, 1]
        final = parse_marian.unwrap_lines(
                result,
                true_ids,
                text_processor=None,
                empties=None,
                n_best=1, 
                expand=True
            )
        answer = [
            "sent0 top1 piece0 sent0 top1 piece1",
            "sent1 top1 piece0 sent1 top1 piece1",
        ]
        self.assertEqual([item['translation'] for item in final], answer)
        [self.assertTrue('nbest_words' in item) for item in final]
        self.assertEqual(len(final), 2)

    def test_unwrap_lines_nbestw_2best_pieces_no_expand(self):
        example = io.StringIO(NBEST_WORDS_2BEST_PIECES)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=2)
        true_ids = [0, 0, 1, 1]
        final = parse_marian.unwrap_lines(
                result,
                true_ids,
                text_processor=None,
                empties=None,
                n_best=2, 
                expand=False
            )
        answer = [
            ["sent0 top1 piece0 sent0 top1 piece1",
            "sent0 top2 piece0 sent0 top2 piece1",],
            ["sent1 top1 piece0 sent1 top1 piece1",
            "sent1 top2 piece0 sent1 top2 piece1"]
        ]
        self.assertEqual([item['translation'] for item in final], answer)
        [self.assertTrue('nbest_words' in item) for item in final]
        self.assertEqual(len(final), 2)

    def test_unwrap_lines_nbestw_2best_pieces_expand(self):
        example = io.StringIO(NBEST_WORDS_2BEST_PIECES)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=2)
        true_ids = [0, 0, 1, 1]
        final = parse_marian.unwrap_lines(
                result,
                true_ids,
                text_processor=None,
                empties=None,
                n_best=2, 
                expand=True
            )
        answer = [
            "sent0 top1 piece0 sent0 top1 piece1",
            "sent0 top2 piece0 sent0 top2 piece1",
            "sent1 top1 piece0 sent1 top1 piece1",
            "sent1 top2 piece0 sent1 top2 piece1",
        ]
        self.assertEqual([item['translation'] for item in final], answer)
        [self.assertTrue('nbest_words' in item) for item in final]
        self.assertEqual(len(final), 4)

    def test_unwrap_lines_nbestw_1best_empty(self):
        example = io.StringIO(NBEST_WORDS_1BEST_EMPTY)
        result = parse_marian.parse_nbest_words(example, n_items=None, n_best=1)
        true_ids = [0, 0]
        final = parse_marian.unwrap_lines(
                result,
                true_ids,
                text_processor=None,
                empties=None,
                n_best=1, 
                expand=True
            )
        answer = [
            ""
        ]
        self.assertEqual([item['translation'] for item in final], answer)
        [self.assertTrue('nbest_words' in item) for item in final]
        self.assertEqual(len(final), 1)


if __name__ == '__main__':
    unittest.main()