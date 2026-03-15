FROM python:3.12-slim

WORKDIR /app

COPY ./api/requirements.txt /tmp/api-requirements.txt
COPY ./workers/requirements.txt /tmp/workers-requirements.txt

RUN pip install --no-cache-dir -r /tmp/api-requirements.txt \
    && pip install --no-cache-dir -r /tmp/workers-requirements.txt

COPY . /app

ENV PYTHONPATH=/app