#!/bin/bash
mosesdecoder=$TOOLS_DIR/tools/mosesdecoder
cat $1 \
    | sed 's/\@\@ //g' \
    | $mosesdecoder/scripts/recaser/detruecase.perl 2>/dev/null \
    | $mosesdecoder/scripts/tokenizer/detokenizer.perl -l en 2>/dev/null \
    | $mosesdecoder/scripts/generic/multi-bleu-detok.perl valid.REF \
    | sed -r 's/BLEU = ([0-9.]+),.*/\1/'
