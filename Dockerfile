# syntax=docker/dockerfile:1
FROM python:3.8-slim

ENV HOME="/root"
WORKDIR /root

# install apt dependencies
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends git curl rclone && \
    curl -sSL https://get.docker.com/ | sh && \
    rm -rf /var/lib/apt/lists/*

# install poetry
ARG PYPI_MIRROR
RUN if [ -n "$PYPI_MIRROR" ]; then pip config set global.index-url $PYPI_MIRROR; fi
RUN --mount=type=cache,target=/root/.cache pip install poetry

# create virtualenv
ENV VIRTUAL_ENV=/root/.venv
RUN python3 -m virtualenv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# install dependencies
ARG PYTEST
COPY pyproject.toml poetry.lock README.md /root/
COPY joj/tiger/__init__.py /root/joj/tiger/
COPY runner/runner /root/runner/runner
COPY toolchains /root/toolchains
RUN --mount=type=cache,target=/root/.cache if [ -n "$PYTEST" ]; then poetry install -vvv -E test; else poetry install -vvv --only main; fi
COPY . /root

CMD python3 -m joj.tiger
