# This Makefile is used inside the Docker container to build MarianNMT,
# and other tools (e.g. moses, subword-nmt, sentencepiece, etc). It also
# includes steps to make it quicker to rerun the docker build and docker run
# commands themselves.

#expose environment variables for docker build and run in this Makefile
include edinmt/configs/env_build.sh
export $(shell sed 's/=.*//' edinmt/configs/env_build.sh)


all: tools python-requirements systems marian


# docker
docker-build:
	docker build -t scriptsmt/systems:$(DOCKER_VERSION) . 

docker-run:
	docker run --gpus all --rm --env-file=edinmt/configs/env_run.sh --name edinmt scriptsmt/systems:$(DOCKER_VERSION) serve 

docker-test:
	docker run --gpus all --rm --env-file=edinmt/configs/env_run.sh --name edinmt scriptsmt/systems:${DOCKER_VERSION} test

docker-save:
	docker save scriptsmt/systems:$(DOCKER_VERSION) > scriptsmt-systems:$(DOCKER_VERSION).tar


#NMT software (note flag to build on cpu arch to work on cpu of downstream users)
marian: marian-dev marian-nbest-words

marian-dev:
	git clone $(MARIAN_REPO_URL) -b $(MARIAN_BRANCH_NAME) $@ && cd $@ && git checkout $(MARIAN_COMMIT_ID)
	mkdir -p $@/build && cd $@/build && cmake .. -DBUILD_ARCH=westmere -DUSE_STATIC_LIBS=on -DCMAKE_BUILD_TYPE=Release -DCOMPILE_SERVER=on -DCOMPILE_CPU=on && make -j && rm -rf src/ local/

marian-nbest-words:
	git clone $(NBEST_WORDS_REPO_URL) -b $(NBEST_WORDS_BRANCH_NAME) $@ && cd $@ && git checkout $(NBEST_WORDS_COMMIT_ID)
	mkdir -p $@/build && cd $@/build && cmake .. -DBUILD_ARCH=westmere -DUSE_STATIC_LIBS=on -DCMAKE_BUILD_TYPE=Release -DCOMPILE_SERVER=on -DCOMPILE_CPU=on && make -j && rm -rf src/ local/


#other tools
tools: tools/moses-scripts tools/subword-nmt tools/sentencepiece

tools/moses-scripts:
	git clone $(MOSES_REPO_URL) -b $(MOSES_BRANCH_NAME) $@
tools/subword-nmt:
	git clone $(SUBWORDNMT_REPO_URL) -b $(SUBWORDNMT_BRANCH_NAME) $@
tools/sentencepiece:
	git clone $(SENTENCEPIECE_REPO_URL) -b $(SENTENCEPIECE_BRANCH_NAME) $@
	mkdir -p $@/build && cd $@/build && cmake .. && make -j


python-requirements:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .

.PHONY: all python-requirements systems.$(MODEL_VERSION) tools
