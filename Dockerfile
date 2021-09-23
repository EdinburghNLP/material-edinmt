FROM nvidia/cuda:11.2.1-cudnn8-devel-ubuntu20.04
ENV DEBIAN_FRONTEND noninteractive

#FROM nvidia/cuda:10.1-cudnn7-devel-ubuntu18.04
#FROM nvidia/cuda:11.0-devel-ubuntu18.04-rc
#FROM nvidia/cuda:11.2.0-cudnn8-devel-ubuntu18.04

RUN apt-get update && apt-get install --no-install-recommends -y \
    wget \
    libboost-dev \
    libboost-all-dev \
    gfortran \
    zlib1g-dev \
    g++ \
    automake \
    autoconf \
    libtool \
    libgoogle-perftools-dev \
    libxml2-dev \
    libxslt1-dev \
    socat \
    python3-dev \
    python3-setuptools \
    checkinstall \
    libreadline-gplv2-dev \
    libncursesw5-dev \
    libsqlite3-dev \
    tk-dev \
    libffi-dev \
    libssl-dev \
    libgdbm-dev \
    libc6-dev \
    libbz2-dev \
    zlib1g-dev \
    libffi-dev \
    supervisor \
    build-essential \
    parallel \
    git \
    vim \
    cmake \
    python3 \
    python3-pip \
&& rm -rf /var/lib/apt/lists/* && ldconfig -v

# download MKL so we can also run Marian on CPU
RUN wget -qO- 'https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS-2019.PUB' | apt-key add - \
    && sh -c 'echo deb https://apt.repos.intel.com/mkl all main > /etc/apt/sources.list.d/intel-mkl.list' \
    && apt-get update \
    && apt-get install --no-install-recommends -y intel-mkl-64bit-2020.0-088

# first download the big systems into the image early 
# so we can rebuild docker faster during development
COPY ./systems.v25.0.0/ /mt/systems/
COPY ./Makefile /mt/Makefile
WORKDIR /mt
COPY ./edinmt/configs /mt/edinmt/configs
RUN make tools
RUN make marian

# now install the other tools/python requirements, and copy cli to /mt for ease
COPY entrypoint.sh setup.py requirements.txt edinmt/cli/* /mt/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY ./edinmt /mt/edinmt
RUN chmod -R +x /mt/
RUN pip3 install --upgrade pip; \
	pip3 install -r requirements.txt; \
	pip3 install -e .

ENTRYPOINT [ "/mt/entrypoint.sh" ]
