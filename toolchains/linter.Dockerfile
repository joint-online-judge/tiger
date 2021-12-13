# syntax=docker/dockerfile:1

ARG UBUNTU_IMAGE_TAG="focal"

FROM ghcr.io/joint-online-judge/buildpack-deps:$UBUNTU_IMAGE_TAG

# install apt dependencies
ENV DEBIAN_FRONTEND="noninteractive"
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    rm -rf /var/cache/apt/archives/lock && \
    apt-get install -y --no-install-recommends  \
        clang-tools clang-format clang-tidy cppcheck  \
    && rm -rf /var/lib/apt/lists/*

# Install pip
RUN --mount=type=cache,target=/root/.cache \
    curl -f https://bootstrap.pypa.io/get-pip.py | python3 && \
    python3 -m pip install black mypy cpplint
