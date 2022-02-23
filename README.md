# JOJ Tiger

[![GitHub](https://img.shields.io/github/license/joint-online-judge/tiger)](https://github.com/joint-online-judge/tiger/blob/master/LICENSE)
[![CI/CD](https://img.shields.io/github/workflow/status/joint-online-judge/tiger/cicd/master)](https://github.com/joint-online-judge/tiger/actions/workflows/ci.yml)
[![GitHub branch checks state](https://img.shields.io/github/checks-status/joint-online-judge/tiger/master)](https://github.com/joint-online-judge/tiger)
[![Codacy Badge](https://img.shields.io/codacy/grade/03b06b5149c6449196fca93a39b25c68)](https://www.codacy.com/gh/joint-online-judge/tiger/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=joint-online-judge/tiger&amp;utm_campaign=Badge_Grade)
[![Codacy Badge](https://img.shields.io/codacy/coverage/03b06b5149c6449196fca93a39b25c68)](https://www.codacy.com/gh/joint-online-judge/tiger/dashboard?utm_source=github.com&utm_medium=referral&utm_content=joint-online-judge/tiger&utm_campaign=Badge_Coverage)

The new generation of JOJ Judge Daemon. "Tiger" is named after "Tiger Machine", or slot machine. It is also inspired by the logo of JI, "Blue Tiger".

## Requirements

+ Python >= 3.7
+ rabbitmq

## Installation

Install <https://github.com/joint-online-judge/autograder-sandbox> first.

### Setup venv (Optional)

```bash
python3 -m venv env
source env/Scripts/activate
```

(get judger JWT from horse)

```bash
pip3 install -e .
python3 -m joj.tiger <JWT>
```

### Run Flower (Optional)

```bash
flower
```

### For developers

```bash
pip3 install -r requirements-dev.txt
pre-commit install
```
