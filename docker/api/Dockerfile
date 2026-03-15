FROM python:3.12-slim

WORKDIR /app

COPY ./api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

ENV PYTHONPATH=/app

EXPOSE 8000