FROM python:3.9.12-alpine3.15

RUN apk update && apk upgrade

# hadolint ignore=DL3018
RUN apk add --no-cache \
        bash \
        curl \
        build-base \
        postgresql-dev

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/etc/poetry python3 -

ENV PATH="/etc/poetry/bin:${PATH}" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_CACHE_DIR=/etc/poetry/

RUN poetry --version

COPY . /src

WORKDIR /src

RUN poetry lock && poetry install -n --without dev

# Require following environment variable:
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# PROD=
# REGION=

CMD ["python", "runner.py"]
