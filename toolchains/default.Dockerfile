# syntax=docker/dockerfile:1

ARG UBUNTU_IMAGE_TAG="focal"

FROM buildpack-deps:$UBUNTU_IMAGE_TAG

ARG UBUNTU_IMAGE_TAG

# useful if the official package registry is too slow
ARG APT_MIRROR
RUN if [ ! -z "$APT_MIRROR" ]; then mv /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb $APT_MIRROR $UBUNTU_IMAGE_TAG main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb-src $APT_MIRROR $UBUNTU_IMAGE_TAG main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb $APT_MIRROR $UBUNTU_IMAGE_TAG-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb-src $APT_MIRROR $UBUNTU_IMAGE_TAG-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb $APT_MIRROR $UBUNTU_IMAGE_TAG-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb-src $APT_MIRROR $UBUNTU_IMAGE_TAG-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb $APT_MIRROR $UBUNTU_IMAGE_TAG-security main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb-src $APT_MIRROR $UBUNTU_IMAGE_TAG-security main restricted universe multiverse" >> /etc/apt/sources.list; fi

# install apt dependencies
ENV DEBIAN_FRONTEND="noninteractive"
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    rm -rf /var/cache/apt/archives/lock && \
    apt-get install -y --no-install-recommends  \
        cmake libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev libgmp-dev \
        llvm clang googletest \
    && rm -rf /var/lib/apt/lists/*

# Install googletest
RUN cd /usr/src/googletest && \
    cmake . && make -j4 && make install && make clean
