# material-edinmt

## Introduction

This is a pipeline for building and releasing machine translation systems. It can be used to translate a directory of small documents, or to run a server.  

The system runs in one [Docker](https://www.docker.com/) container, which uses the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker) to expose GPUs. The Dockerfile incorporates a Makefile to build some of the dependencies. Additional scripts are also included that can invoke the `marian-decoder` directly (rather than going through the server) to make translations.  

## Supported language directions and features

Supported language directions include English to/from Swahili, Tagalog, Somali, Lithuanian, Bulgarian, Farsi, Kazakh, and Georgian. Not all language directions support all features. The following table lists the features supported for each language direction (as of models v25.0.0).

- Text is normal text translation.
- Audio are models that were trained with ASR outputs in mind.
- Query are models that support query guided translation.

|       |text |audio |query  |
|-------|-----|------|-------|
|en<>sw |ok   |N/A   |N/A    |
|en<>tl |ok   |N/A   |N/A    |
|en<>so |ok   |ok    |N/A    |
|en<>ps |ok   |N/A   |N/A    |
|en<>lt |ok   |N/A   |N/A    |
|en<>bg |ok   |N/A   |N/A    |
|en<>fa |ok   |ok    |N/A    |
|en<>kk |ok   |ok    |kk->en |
|en<>ka |ok   |ok    |ka->en |

## Requirements

- [Docker](https://www.docker.com/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker) (to use GPUs)


## Run the Docker translator to translate a single folder

The Docker image comes with a translation function that translates input folders on the command line. To use this functionality, you need to mount volumes in the docker container.

To run the translate command, first edit `edinmt/configs/env_run.sh` with your settings for these options (you could also pass these environment variables to docker using the `-e` flag, but a separate file is easier to maintain):

```
SRC=kk              #source language (used to infer the system to run) 
TGT=en              #target language (used to infer the system to run)
DEVICES=0,1         #GPUs to run the servers on (if this is missing, will run on CPUs by default)
MODE=fast           #"fast" to use 1 model for translation (default is "accurate" to use a slower ensemble)
TYPE=text           #"text" to use a normal MT model, "audio" to use one optimised for speech translation
NBEST=0             #output n-best sentences (`n` is determined by the beam size in the marian model config)
NBEST_WORDS=0       #output the n-best tokens in each position in each sentence (using Alham's decoder)
QUERY=0             #use query guided machine translation (only available in some models)
FMT=json            #output format of "json", "marian", "text" (default is "json" for json-lines format)
```

To use the docker container to translate a folder, you will need to use the `-v` flag to mount the input and output directory into the container. Note that the directories need to be located where docker has read/write permissions. 

```
docker run --gpus all --rm -v ~/input_dir:/mt/input_dir -v ~/output_dir:/mt/output_dir --env-file=edinmt/configs/env_run.sh --name edinmt scriptsmt/systems:v25.0.0 translate src_lang tgt_lang /mt/input_dir /mt/output_dir
```

NOTE: This command passes any additional unrecognized arguments directly to the [marian-decoder](https://marian-nmt.github.io/docs/cmd/marian-decoder/), which override any pre-set environment variables.

### Query-guided translation feature

For those systems that support query-guided translation, in addition to setting the QUERY=1 option, queries should be incorporated in the input files as a second tab-separated field. The query-guided systems can still translate without queries (e.g. in case some sentences don’t require or are missing queries), but performance may be slightly lower than using a non-query-guided system without queries.


## Fine-tune a pre-trained model 

The Docker container can be used to fine-tune one of our pre-trained models on your own training and validation data. To use this functionality, you need to mount volumes in the docker container which contain your train/valid data, and provide the `finetune` command with the filepath arguments, e.g.:

```
docker run --gpus all --rm -v ~/data:/mt/data -v ~/finetuned_dir:/mt/finetuned_dir --env-file=edinmt/configs/env_run.sh --name edinmt scriptsmt/systems:v25.0.0 finetune fa en /mt/finetuned_dir --train /mt/data/train.fa /mt/data/train.en --valid /mt/data/valid.fa /mt/data/valid.en
```

NOTE: We use an internal train config for this command, but we do pass any additional unrecognized arguments directly to the [marian](https://marian-nmt.github.io/docs/cmd/marian/) afterwards, which override any pre-set environment variables and the internal config.

### Translate with a fine-tuned model

The fine-tuned model can then be used to translate folders (same command as above) by changing the SYSTEMS_DIR environment variable to point to the directory where the model was created. The directory will need to be re-mounted using the docker `-v` flag.

```
docker run --gpus all --rm -v ~/finetuned_dir:/mt/finetuned_dir -v ~/input_dir:/mt/input_dir -v ~/output_dir:/mt/output_dir -e SYSTEMS_DIR=/mt/finetuned_dir --name edinmt scriptsmt/systems:v25.0.0 translate src_lang tgt_lang /mt/input_dir /mt/output_dir
```

## Run the Docker translation server

The Docker image comes with a translation server that runs on a websocket connection and accepts json inputs. 

We use the `marian-server` of [MarianNMT](https://marian-nmt.github.io/) to serve inference. We connect to the `marian-server` through our own a python translation server, which includes the necessary data preprocessing layers (e.g. byte-pair encoding, tokenization, etc.). 

To launch the server, first edit `edinmt/configs/env_run.sh` with your settings for the same options as in the translator (or use the `-e` environment flags). Then start the docker container with the `serve` directive:

```
docker run --gpus all --rm --env-file=edinmt/configs/env_run.sh --name edinmt scriptsmt/systems:v25.0.0 serve
```

The server accepts json input. Here is a python example (input sentences separated by `\n`):

```
import json
import websocket

all_input = json.dumps(
   {
      'src_lang': 'fa', 
      'tgt_lang': 'en', 
      'text': 'ما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.\nما در "برکلی بایونیکس" به این روبات‌‌ها اگزو اسکلت می‌گوئیم.',
      'query': 'the query string'
   }
)

ws = websocket.create_connection("ws://localhost:8081/")
ws.send(all_input)
result = ws.recv()

print(result)

ws.close()
```

The resulting translations will be returned on the websocket connection as an ordered list of json-lines. In case the system is set to return n-best translations, the output will be ordered with the best translation coming first, e.g:

```
{"id": 0, "translation": "The best translation for sentence 0."}
{"id": 0, "translation": "The second best translation for sentence 0."}
...
{"id": 1, "translation": "The best translation for sentence 1."}
{"id": 1, "translation": "The second best translation for sentence 1."}
```

TODO: convert the pipeline server to FastAPI or similar, which includes automatic swagger documentation?

## Running multiple servers

Each docker container runs only one system, but multiple systems (both servers and translators) can be run from the same image. To run multiple systems, invoke `docker run` multiple times (with separate configurations/arguments). 

For running the server with `serve`, you may wish to map the ports in this case. By default, each container runs the marian-server on 8080 and the translation pipeline server on 8081 internally, so if you may want to redirect those ports to something else on your host machine. In this case, please ensure you use different GPUs for each container. For example:

```
docker run --gpus all --rm --env-file=env_faen.sh -e DEVICES=0,1 -p 2012:8080 -p 3012:8081 --name faen scriptsmt/systems:v25.0.0 serve 
docker run --gpus all --rm --env-file=env_enfa.sh -e DEVICES=2,3 -p 2013:8080 -p 3013:8081 --name enfa scriptsmt/systems:v25.0.0 serve
```

TODO: We could automate this with docker-compose instead? Does the nvidia runtime work in the latest version (https://github.com/docker/compose/issues/6691)? 

## Building the Docker image

The Makefile includes commands for `docker-build` for convenience. You can always invoke `docker build` manually with your own settings instead. 

To build, you will need the model directory, which contains subdirectories for each of the translation directions, e.g. `systems.v25.0.0`. The directory should contain all of the necessary vocab, bpe model, truecase model, the MT models themselves, marian config files, etc., for example:

```
...
├── enka
│   ├── bpe.model
│   ├── bpe.vocab
│   ├── config-fast.yml
│   ├── config.yml
│   ├── model1.npz
│   ├── model2.npz
│   ├── model3.npz
│   ├── model4.npz
│   ├── validate.sh
│   └── vocab.yml
├── faen
│   ├── config-fast.yml
│   ├── config.yml
│   ├── faen.bpe
│   ├── model1.npz
│   ├── model2.npz
│   ├── model3.npz
│   ├── model4.npz
│   ├── tc.fa
│   ├── train.yml
│   ├── validate.sh
│   └── vocab.yml
...
``` 

To build, edit the variables in `edinmt/configs/env_build.sh` and then run:

```
make docker-build
```

This is equivalent to:

```
docker build -t scriptsmt/systems:${DOCKER_VERSION} .
```

where `${DOCKER_VERSION}` is found in `env_build.sh` by the `Makefile`.

Note that the `env_build.sh` variables also include a `MODEL_VERSION`, which is downloaded from `http://data.statmt.org/<user_name>/scriptsmt/systems.<model_version>`. 


## For Developers

### Creating a new release

#### Adding text pre-/post-processing plugins

If your model uses a new data pre-/post-processing pipeline (very likely), then you will first want to add some plugins for this, which reside in the `edinmt/text_processors` folder. These are used to convert the data into inputs that the marian model is aware of, e.g. using BPE or moses tokenization, and then to convert model outputs into readable text line-by-line, before returning json-lines format (this occurs in pipeline.py).

You can write any type of python code for your own processor, including invoking stand-alone shell scripts using `subprocess`. To add a new processor to the pipeline, create a new python module in the edinmt/processors directory, and update `edinmt.configs.config.Config.SYSTEM_TO_TEXT_PROCESSOR` with an exception for your language direction and processor (with the same name as your processor class name). Adhereing to this interface and naming scheme helps translate.py dynamically find your code. The new processor you write must inherit from `edinmt.text_processors.text_processors.TextProcessor`. This helps the translation code to know exactly how to talk to the processor. 

#### Release

Next, follow these steps to create a new docker image and publish a new version of this repo:

1. Update `edinmt/configs/env_build.sh` with a new model version and other docker build settings.
2. Update `edinmt/configs/env_run.sh` with your settings which will be used during docker run.
3. Update `edinmt/configs/config.py` with the appropriate settings for your model.
4. Build and launch the docker servers to test that everything works:
```
make docker-build
make docker-run
```
5. Test that everything runs correctly (this will take some minutes since we test translations): 
```
make docker-test
```
6. Save the docker into a tar file:
```
make docker-save
```
7. Update this README.md with anything that might have changed and *please be super detailed!* 
8. Add your changes for this repo:
```
git add <your-changed-files>
```
9. Commit to Git using Conventional Commit format:
```
cz commit
```
10. Create a new tagged commit with an updated semver number and git tag, e.g. using semantic-release: 
```
semantic-release version
```
11. Update the changelog, and edit CHANGELOG.md with the new semantic release version and date: 
```
mv CHANGELOG.md CHANGELOG.md.bck; cat <(semantic-release changelog) CHANGELOG.md.bck > CHANGELOG.md
git add CHANGELOG.md; git commit --amend
```
12. Push to GitHub: 
```
git push
git push --tags
```

TODO: add Github Actions for release?

### MATERIAL Requirements

This docker build is primarily intended to serve the MATERIAL project, and requirements were gathered through trial and error with the other groups that work on the MATERIAL project at other institutions.

*Entrypoints:*
- The docker container must run a translation server which can be queried over websockets. This may be one entrypoint.
- The docker container must run a "batch translation" script over the command line using `docker run` or `docker exec`. This may be an additional entrypoint.
- The "batch translation" entrypoint must translate an entire input directory to an output directory (volumes will be mounted by the user using docker's `-v` flag).
- Batch translation may query the running server or may inoke marian-decoder directly. 
   - Invoking the marian-decoder directly allows us to bypass issues with the marian-server implementation, lets us avoid allocating server resources when a server is not needed, therefore, we have chosen this method.

*Outputs:*
- The batch translation entrypoint must provide an option to return outputs in json-lines format, marian format (with `' ||| '` delimiters), or plaintext format
- API through docker flag: `-e FMT='json'` (options include: `'json', 'marian', 'text'`)

*GPUs:*
- The docker container must be able to use GPUs for both the server and batch translation. 
- The server and batch translation scripts should manage GPU usage to make sure all the GPUs are used efficiently. 
- API through docker flag: `-e DEVICES=0,1,2,3`
   - Note: the flag must accept commas because the users have difficulty passing spaces through their other software.

*Language directions:*
- The docker container must include all possible systems/language directions for translation.
- The specific system to be used must be inferred by the container from the user's source/target languages, and should not be selected explicitly by the user.

*Mode (fast/accurate):*
- The docker container must allow the user to prioritize translation speed over translation accuracy.
   - This has been typically implemented in separate marian config files for each system which cover translations using 1 model for speed vs. translations using a slower ensemble of 4 top models for accuracy.
- API through docker flag: `-e MODE=fast` and `-e MODE=accurate` (default is accurate)

*Type (text/audio):*
- The docker container must allow the user to choose a system optimized for speech translation.
- The correct system to be used should be inferred through an environment variable, and should not to be selected explicitly by the user.
- API through docker flag: `-e TYPE=text` and `-e TYPE=audio` (default is text)

*N-best sentences:*
- The docker container must provide an option for retrieving n-best translations. 
- API through docker flag: `-e NBEST=1`

*N-best words:*
- The docker container must provide an option for retrieving n-best tokens in each position, e.g. using Alham's decoder implementation, available here: [https://github.com/afaji/Marian/tree/alt-words](https://github.com/afaji/Marian/tree/alt-words)
- API through docker flag: `-e NBEST_WORDS=1`

*Other API options:*
- The docker container must not require any other settings than the ones described above to run the system. It may expose other settings as options, however.

### Debugging 

For debugging the Docker container, use `-e DEBUG=True`, which will save all temporary files and split out the marian log files. See also `edinmt/configs/config.py` for the full list of environment variables (including paths for directories) that are read by the system.

### Code walkthrough

The following is a brief walkthrough of some of the included files, to aid in development and debugging:

- *Dockerfile*: creates the docker image

- *entrypoint.sh*: the Docker entrypoint with `serve` and `translate` directives (`serve` invokes supevisord)

- *Makefile*: used for building both the docker, and the internal systems
   - Includes `docker-build` and `docker-run` commands, which read from configs so developer-users only need to make small changes to rebuild with new settings.
   - Contains commands to build tools and systems, which can be used by developer-users to build everything locally (outside of Docker) and which are also used by the Dockerfile to build tools and systems.

- *setup.cfg*: used by python-semantic-release to automate version control 
   - Note: commitizen may give a warning about this file, which is safe to ignore.

- *setup.py*: used to install the python package as `edinmt`
   - Installing this way ensures absolute imports always work and helps track the codebase version. 
   - It is recommended that you install this package into an environment (e.g. from conda or virtualenv). You can install it using `pip install -e .`.

- *supervisord.conf*: supervisord manages the server processes and keeps the container running


- *edinmt/get_settings.py*: the code here combines environment variables with user settings to get the final settings to invoke the marian-decoder or marian-server (e.g. finding the config files, setting up the devices command, etc.). We use a mutli-tiered system, in which environment variables are read from first (if unspecified, a default is used), and then CLI arguments overwrite them. 

- *edinmt/parse_marian.py*: parse the output from marian-decoder (e.g. read the lines with ||| and take care of numbering the final output sentence ids correctly)
- *_TODO_*: the parser is disasterously inefficient for big files, since it was assumed we'd have a directory of small files like in the MATERIAL project. This is the biggest problem in scalability right now.

- *edinmt/translate_folder.py*: functions that read inputs from files, send it to translation (to marian-decoder or to the running server), invoke the parsers, and write the output back to files in an output directory using the same directory structure

- *edinmt/translate_input.py*: functions that read inputs from stdin, send it to translation (to marian-decoder or to the running server), invoke the parsers, and write the output back to stdout.

- *edinmt/utils.py*: small bits of code re-used in other places around this package

- *edinmt/cli/*: command-line interface scripts which also get copied into /mt in the Docker for convenience

- *edinmt/cli/finetune.py*: fine-tune a pre-existing model from the SYSTEMS_DIR using a custom train/dev dataset, but using the same preprocessing steps as the original model used 

- *edinmt/cli/translate_input.py*: translate using the pipeline on stdin/stdout using pre-built marian-decoder

- *edinmt/cli/translate_folder.py*: translate a folder of documents using pre-built marian-decoder. This is optimized to work on many small files; in particular, the postprocessing step is currently very slow when working with one big file. TODO: refactor this step.

- *edinmt/cli/prepare_training_data.py*: preprocess a dataset using the same preprocessing steps as were used by the original model (e.g. SPM bpe, Moses bpe, etc.). This is done by invoking the text_processor.prepare_training_data function 

- *edinmt/cli/score_test_sets.py*: score your own test sets using the available scorers (e.g. SacrebleuScorer)


- *edinmt/configs/*: central location for any type of configuration files

- *edinmt/configs/config.py*: configs to launch the servers/text processors, including ROOT_DIR for `edinmt` and the MT system directories

- *edinmt/configs/env_build.sh*: config for `docker build`, including URLs of where to download systems and tools, the MODEL_VERSION, and other docker build settings

- *edinmt/configs/env_run.sh*: config for the `docker run`, including settings such as DEVICES for which GPUs marian-server should use, etc.

- *edinmt/configs/train.DEFAULT.yml*: default config (with relative paths) to use for marian when fine-tuning a model, which is used in case the system model directory doesn't have a train.yml file included, and which gets copied into the output finetuning directory

- *edinmt/configs/validate_DEFAULT.sh*: default validate script (with relative paths) referenced in train.DEFAULT.yml, which is used in case the system model directory doesn't have a validate.sh file included, and which gets copied into the output finetuning directory


- *edinmt/extras/*: extra scripts that can be useful in MT in general, but are not invoked by the translation system directly, but which we don't have a better place for yet


- *edinmt/launch/*: central location for any scripts having to do with launching servers and the server APIs

- *edinmt/launch/launch_marian_server.py*: the script that launch the marian-server, invoked by supervisord 

- *edinmt/launch/launch_pipeline_server.py*: the script that launch the pipeline server, invoked by supervisord


- *edinmt/tests/*: tests that can be easily run `python3.7 -m unittest discover edinmt`, or on their own (you will need to have your environment set up and servers launched for some of the tests; otherwise, run them from within the running docker container)


- *edinmt/text_processors/*: directory from which code gets automatically loaded as plugins for text processing (e.g. byte-pair encoders, tokenizers, etc.). 

- *edinmt/text_processors/text_processors.py*: classes to inherit from for your own pre-/post- text processors, including some basic text processors such as SPM, Moses, Subword-NMT, Multilingual tagging, etc.

- *edinmt/text_processors/composite_processors.py*: combines basic text processors together (e.g. moses+subword-nmt or multilingual+spm, etc.) 


- *edinmt/scorers/*: directory from which code gets automatically loaded as plugins for scoring, e.g. SacreBLEU scorer 

- *edinmt/scorers/scorers.py*: classes to inherit from for your own pre-/post- text processors, including some basic scorers such as SacreBleu 


### Exploring the Docker container

You can run a Docker container to drop into an interactive bash shell and explore the code in the image using:

```
docker run -it --entrypoint /bin/bash scriptsmt/systems:${DOCKER_VERSION}
```



