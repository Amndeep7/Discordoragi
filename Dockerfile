FROM ubuntu:latest

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml .

RUN apt update && apt install -y tree vim postgresql-client build-essential libssl-dev libffi-dev python3 python3-dev python3-pip python3-venv && pip install pipx && pipx install poetry && poetry install

COPY . .
