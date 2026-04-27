FROM python:slim

RUN apt-get update && apt-get install fonts-terminus

RUN pip install websocket-client

RUN mkdir -p /app

WORKDIR /app

COPY dfplex_client.py /app/dfplex_client.py

ENTRYPOINT [ "python", "/app/dfplex_client.py" ]
