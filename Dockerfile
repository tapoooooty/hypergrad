FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=UTC

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY hip3 ./hip3
COPY web ./web
COPY economics ./economics
COPY config.json .

RUN useradd --create-home --uid 10001 hypergrad && mkdir -p /app/state && chown -R hypergrad /app
USER hypergrad

ENTRYPOINT ["python", "-m", "hip3"]
CMD ["doctor"]
