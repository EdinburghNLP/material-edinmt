#!/bin/bash
COMMAND=$1

if [ $COMMAND == "serve" ]
then
    /usr/bin/supervisord
elif [ $COMMAND == "translate" ]
then
    echo "translate_folder.py ${@:2}"
    python3 edinmt/cli/translate_folder.py "${@:2}"
elif [ $COMMAND == "finetune" ]
then
    echo "finetune.py ${@:2}"
    python3 edinmt/cli/finetune.py "${@:2}"
elif [ $COMMAND == "score" ]
then
    echo "score_file.py ${@:2}"
    python3 edinmt/cli/score_file.py "${@:2}"
elif [ $COMMAND == "test" ]
then
    echo "python3 -m unittest discover -v /mt/edinmt/tests"
    python3 -m unittest discover -v
else
    echo "ERROR: first argument must one of: 'serve', 'translate', 'finetune', 'score', 'test'"
    exit 1
fi
