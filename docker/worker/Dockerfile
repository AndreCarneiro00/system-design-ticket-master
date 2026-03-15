FROM python:3.12-slim

WORKDIR /app

COPY ./api/requirements.txt /tmp/api-requirements.txt
COPY ./worker/requirements.txt /tmp/worker-requirements.txt

RUN pip install --no-cache-dir -r /tmp/api-requirements.txt \
    && pip install --no-cache-dir -r /tmp/worker-requirements.txt

COPY ./api /app
COPY ./worker /app/worker